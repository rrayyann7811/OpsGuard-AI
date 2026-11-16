import asyncio
from datetime import datetime, timezone
from time import perf_counter
import httpx


def utc():
    return datetime.now(timezone.utc).isoformat()


class ServiceMonitor:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport
        self.stop_event = asyncio.Event()
        self.urls = {name: getattr(settings, name.replace("-service", "_service_url")) for name in ("user-service", "order-service", "payment-service")}
        self.states = {name: dict(service_name=name, status="Unknown", available=None,
            last_success=None, last_attempt=None, latency_ms=None, failure_reason=None,
            consecutive_failures=0) for name in self.urls}

    async def check(self, client, name, url):
        old = self.states[name]
        state = {**old, "last_attempt": utc()}
        started = perf_counter()
        try:
            response = await client.get(url.rstrip("/") + "/health")
            response.raise_for_status()
            data = response.json()
            if data.get("success") is not True or data.get("data", {}).get("service") != name or data.get("data", {}).get("status") != "healthy":
                raise ValueError("Invalid health contract")
            latency = round((perf_counter() - started) * 1000, 2)
            state.update(status="Degraded" if latency > self.settings.monitor_degraded_ms else "Healthy",
                         available=True, latency_ms=latency, last_success=utc(), failure_reason=None, consecutive_failures=0)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as error:
            reason = ("Health request timed out" if isinstance(error, httpx.TimeoutException)
                      else f"Health endpoint returned HTTP {error.response.status_code}" if isinstance(error, httpx.HTTPStatusError)
                      else "Health endpoint unreachable" if isinstance(error, httpx.RequestError)
                      else "Invalid health response")
            failures = old["consecutive_failures"] + 1
            state.update(status="Unavailable" if failures >= 3 else "Degraded", available=False,
                         latency_ms=round((perf_counter() - started) * 1000, 2),
                         failure_reason=reason, consecutive_failures=failures)
        self.states[name] = state

    async def tick(self, client):
        await asyncio.gather(*(self.check(client, name, url) for name, url in self.urls.items()))

    async def run(self):
        async with httpx.AsyncClient(timeout=max(.05, self.settings.monitor_timeout_seconds), transport=self.transport, follow_redirects=False) as client:
            while not self.stop_event.is_set():
                await self.tick(client)
                try:
                    await asyncio.wait_for(self.stop_event.wait(), max(.1, self.settings.monitor_interval_seconds))
                except asyncio.TimeoutError:
                    pass

    def stop(self):
        self.stop_event.set()
