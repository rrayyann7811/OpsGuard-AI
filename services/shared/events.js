import { randomUUID } from "node:crypto";

export function incidentEvent(service, request, error, status, duration) {
  return {
    event_id: randomUUID(),
    service_name: service,
    timestamp: new Date().toISOString(),
    severity: status >= 500 ? "error" : "warning",
    error_type: error.type,
    error_message: error.message,
    stack_trace: error.stack ?? null,
    http_status: status,
    request_id: request.id,
    endpoint: request.path,
    duration_ms: duration,
  };
}

// A bounded, best-effort adapter. A future Phase 3 transport can be injected.
// No HTTP ingestion endpoint or persistence is implemented here.
export function createPublisher({
  transport = async () => {},
  onFailure = () => {},
  timeoutMs = 100,
  maxPending = 16,
} = {}) {
  let pending = 0;
  return async (event) => {
    if (pending >= maxPending) return false;
    pending++;
    const controller = new AbortController();
    let timer;
    try {
      const task = Promise.resolve()
        .then(() => transport(event, { signal: controller.signal }))
        .finally(() => {
          pending--;
        });
      await Promise.race([
        task,
        new Promise((_, reject) => {
          timer = setTimeout(() => {
            controller.abort();
            reject(new Error("Publication timed out"));
          }, timeoutMs);
        }),
      ]);
      return true;
    } catch {
      try {
        onFailure();
      } catch {
        /* Logging must not break the caller. */
      }
      return false;
    } finally {
      clearTimeout(timer);
    }
  };
}

// One bounded delivery operation; retry uses the identical event_id and payload.
export function httpTransport({
  url,
  token,
  fetcher = fetch,
  attempts = 3,
  attemptTimeoutMs = 500,
}) {
  const target = new URL(url);
  if (
    !["http:", "https:"].includes(target.protocol) ||
    target.username ||
    target.password
  )
    throw new Error("Invalid incident ingestion URL");
  if (!token) throw new Error("Incident webhook token is required");
  return async (event, { signal }) => {
    for (
      let attempt = 0;
      attempt < Math.min(3, Math.max(1, attempts));
      attempt++
    ) {
      let retry = true;
      try {
        const response = await fetcher(target, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(event),
          signal: AbortSignal.any([
            signal,
            AbortSignal.timeout(attemptTimeoutMs),
          ]),
          redirect: "error",
        });
        const status = response.status;
        await response.body?.cancel();
        if (response.ok) return;
        retry = status === 429 || status >= 500;
      } catch {
        if (signal.aborted) throw new Error("Incident delivery aborted");
      }
      if (!retry) throw new Error("Incident rejected");
      if (attempt < Math.min(3, Math.max(1, attempts)) - 1) {
        const { setTimeout } = await import("node:timers/promises");
        await setTimeout(50 * (attempt + 1), null, { signal });
      }
    }
    throw new Error("Incident delivery failed");
  };
}
