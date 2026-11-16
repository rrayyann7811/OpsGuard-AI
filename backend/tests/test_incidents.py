import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.config import Settings
from app.models import Incident, IncidentEvent, now
from app.monitor import ServiceMonitor
from app.incidents import EventInput, signature

TOKEN = "disposable-webhook-test-key"
HEADERS = {"Authorization": "Bearer " + TOKEN}


def event(**kwargs):
    return dict(event_id=str(uuid4()), service_name="payment-service", timestamp=datetime.now(timezone.utc).isoformat(),
        severity="error", error_type="PaymentFailure", error_message="Processor rejected payment", stack_trace="Processor rejected payment\n at process (/app/shared/app.js:20:3)", http_status=502,
        request_id=str(uuid4()), endpoint="/simulate/:scenario", duration_ms=1.2, **kwargs)


@pytest.fixture
def api(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "incidents.db"), connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)
    settings = Settings(monitor_enabled=False, incident_webhook_token=TOKEN, incident_management_token=TOKEN,
                        enable_incident_management=True, environment="development")
    def session():
        with factory() as db: yield db
    app.dependency_overrides[get_db] = session
    with patch("app.main.engine", engine), patch("app.main.settings", settings), patch("app.incidents.get_settings", return_value=settings):
        with TestClient(app, client=("127.0.0.1", 50000)) as client:
            yield client, factory, settings
    app.dependency_overrides.clear()
    engine.dispose()


def post(client, payload=None):
    response = client.post("/api/incidents/events", headers=HEADERS, json=payload or event())
    assert response.status_code == 200, response.text
    return response.json()


def test_ingestion_contract_and_preserved_evidence(api):
    client, factory, _ = api
    payload = EventInput.model_validate(event()).model_dump(mode="json")
    data = post(client, payload)
    row = data["incident"]
    assert row["status"] == "OPEN" and row["occurrence_count"] == 1
    assert row["severity"] == "high" and len(row["error_signature"]) == 64
    events = client.get(f"/api/incidents/{row['id']}/events").json()["items"]
    assert all(events[0][key] == value for key, value in payload.items())
    with factory() as db:
        assert db.scalar(select(IncidentEvent)).evidence == payload
    assert client.get(f"/api/incidents/{row['id']}").json()["incident"]["id"] == row["id"]


@pytest.mark.parametrize("updates", [{"event_id":"bad"}, {"timestamp":"2026-01-01"}, {"service_name":"other"}, {"duration_ms":-1}, {"severity":"critical"}, {"http_status":200}, {"extra":"secret"}, {"error_type":" "}])
def test_invalid_payload(api, updates):
    client, _, _ = api
    assert client.post("/api/incidents/events", headers=HEADERS, json={**event(), **updates}).status_code == 422


def test_auth_size_and_safe_validation(api):
    client, _, settings = api
    assert client.post("/api/incidents/events", json=event()).status_code == 401
    assert client.post("/api/incidents/events", headers={"Authorization":"Bearer wrong"}, json=event()).status_code == 401
    assert client.post("/api/incidents/events", headers=[(b"authorization", b"Bearer \xff")], json=event()).status_code == 401
    settings.incident_webhook_token = ""
    assert client.post("/api/incidents/events", headers=HEADERS, json=event()).status_code == 503
    settings.incident_webhook_token = TOKEN
    assert client.post("/api/incidents/events", headers=HEADERS, content='x'*33000).status_code == 413
    response = client.post("/api/incidents/events", headers=HEADERS, json={**event(), "service_name":"secret-password"})
    assert "secret-password" not in response.text


def test_idempotency_and_deduplication(api):
    client, _, _ = api
    payload = event()
    first = post(client, payload)["incident"]
    assert post(client, payload)["duplicate"] is True
    related = {**event(), "error_message":"  Processor   rejected payment  ", "stack_trace":"Processor rejected payment\n at process (/different/checkout/shared/app.js:300:99)"}
    repeated = post(client, related)["incident"]
    assert repeated["id"] == first["id"] and repeated["occurrence_count"] == 2
    assert client.get(f"/api/incidents/{first['id']}/events").json()["total"] == 2
    for update in [{"service_name":"order-service"}, {"error_type":"OtherFailure"}, {"error_message":"Processor rejected refund"}, {"endpoint":"/different"}, {"stack_trace":"error\n at refund (/app/refund.js:2:2)"}]:
        assert post(client, {**event(), **update})["incident"]["id"] != first["id"]


def test_window_resolution_and_reopening(api):
    client, factory, settings = api
    first = post(client)["incident"]
    with factory() as db:
        row = db.get(Incident, first["id"])
        row.last_received_at = now() - timedelta(seconds=settings.dedup_window_seconds + 1)
        db.commit()
    second = post(client)["incident"]
    assert first["id"] != second["id"]
    url = f"/api/incidents/{second['id']}/status"
    assert client.patch(url, headers=HEADERS, json={"status":"RESOLVED"}).status_code == 409
    for status in ["INVESTIGATING", "RESOLVED"]:
        assert client.patch(url, headers=HEADERS, json={"status":status}).status_code == 200
    assert post(client)["incident"]["id"] != second["id"]
    assert client.patch(url, headers=HEADERS, json={"status":"OPEN"}).json()["incident"]["status"] == "OPEN"
    assert client.patch(url, headers=HEADERS, json={"status":"BAD"}).status_code == 422
    settings.enable_incident_management = False
    assert client.patch(url, headers=HEADERS, json={"status":"OPEN"}).status_code == 403


def test_management_auth_and_missing_records(api):
    client, _, _ = api
    row = post(client)["incident"]
    assert client.patch(f"/api/incidents/{row['id']}/status", json={"status":"INVESTIGATING"}).status_code == 401
    missing = str(uuid4())
    for suffix in ["", "/events"]:
        assert client.get(f"/api/incidents/{missing}{suffix}").status_code == 404
    assert client.patch(f"/api/incidents/{missing}/status", headers=HEADERS, json={"status":"OPEN"}).status_code == 404
    assert client.get('/api/incidents/not-a-uuid').status_code == 422


def test_filters_pagination_summary_and_timestamp_order(api):
    client, _, _ = api
    post(client)
    post(client, {**event(), "service_name":"user-service", "severity":"warning", "http_status":401, "error_type":"AuthenticationError"})
    result = client.get('/api/incidents?page_size=1').json()
    assert result["total"] == 2 and len(result["items"]) == 1
    assert client.get('/api/incidents?page=2&page_size=1').json()["items"][0]["id"] != result["items"][0]["id"]
    for query in ["service=user-service", "severity=medium", "search=AuthenticationError"]:
        assert client.get('/api/incidents?' + query).json()["total"] == 1
    assert client.get('/api/incidents?status=RESOLVED').json()["total"] == 0
    assert client.get('/api/incidents?search=%25').json()["total"] == 0
    assert client.get('/api/incidents?page_size=1000').status_code == 422
    summary = client.get('/api/incidents/summary').json()
    assert summary["active"] == 2 and sum(x["events"] for x in summary["history"]) == 2
    assert len(client.get('/api/services').json()["items"]) == 3


def test_redaction_before_persistence(api):
    client, factory, _ = api
    payload = {**event(), "error_message":"token=secret-token password=secret-password Bearer secret-bearer ada@example.test https://user:secret-userinfo@example.test", "endpoint":"/payments?token=secret-query"}
    result = post(client, payload)
    assert "secret-" not in str(result)
    with factory() as db:
        assert "secret-" not in str(db.scalar(select(IncidentEvent)).evidence)


def test_concurrent_duplicate_delivery(api):
    client, _, _ = api
    payload = event()
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: client.post('/api/incidents/events', headers=HEADERS, json=payload), range(4)))
    assert all(response.status_code == 200 for response in responses)
    assert sum(not response.json()["duplicate"] for response in responses) == 1
    assert client.get('/api/incidents').json()["items"][0]["occurrence_count"] == 1


def test_sqlite_restart_persistence(api):
    client, factory, _ = api
    row = post(client)["incident"]
    engine = factory.kw["bind"]
    engine.dispose()
    with factory() as fresh:
        assert fresh.get(Incident, row["id"]).occurrence_count == 1
        assert fresh.scalar(select(IncidentEvent)).incident_id == row["id"]


def test_health_monitor_failure_recovery_and_stop():
    async def run():
        settings = Settings(monitor_interval_seconds=.1)
        broken = False
        async def handler(request):
            if broken: return httpx.Response(503)
            name = request.url.host.split('.')[0] + '-service'
            return httpx.Response(200, json={"success":True,"data":{"service":name,"status":"healthy"}})
        settings.user_service_url = 'http://user.test'
        settings.order_service_url = 'http://order.test'
        settings.payment_service_url = 'http://payment.test'
        monitor = ServiceMonitor(settings, httpx.MockTransport(handler))
        assert monitor.states['payment-service']['status'] == 'Unknown'
        async with httpx.AsyncClient(transport=monitor.transport) as http:
            await monitor.tick(http)
            assert all(s['status']=='Healthy' for s in monitor.states.values())
            broken = True
            await monitor.tick(http)
            assert monitor.states['payment-service']['status'] == 'Degraded'
            await monitor.tick(http); await monitor.tick(http)
            assert monitor.states['payment-service']['status'] == 'Unavailable'
            broken = False
            await monitor.tick(http)
            assert monitor.states['payment-service']['consecutive_failures'] == 0
        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0)
        monitor.stop()
        await asyncio.wait_for(task, 1)
    asyncio.run(run())


def test_source_timestamp_bounds_and_numeric_evidence(api):
    client, _, _ = api
    original = event()
    first = post(client, original)["incident"]
    older = {**event(), "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
    second = post(client, older)["incident"]
    assert second["id"] == first["id"]
    assert second["first_seen"] < first["first_seen"] and second["last_seen"] == first["last_seen"]
    a = post(client, {**event(), "error_message":"Account 123 rejected"})["incident"]
    b = post(client, {**event(), "error_message":"Account 456 rejected"})["incident"]
    assert a["id"] != b["id"]


@pytest.mark.parametrize("mode", ["timeout", "malformed", "wrong-service"])
def test_monitor_rejects_invalid_health(mode):
    async def run():
        async def handler(request):
            if mode == "timeout": raise httpx.ReadTimeout("private-network-details")
            if mode == "malformed": return httpx.Response(200, text="not-json")
            return httpx.Response(200, json={"success":True,"data":{"service":"wrong","status":"healthy"}})
        monitor = ServiceMonitor(Settings(), httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=monitor.transport) as client:
            await monitor.tick(client)
        assert all(state["available"] is False for state in monitor.states.values())
        assert all("private-network-details" not in str(state) for state in monitor.states.values())
    asyncio.run(run())


def test_management_remote_client_and_cors(api):
    client, _, settings = api
    row = post(client)["incident"]
    from starlette.requests import Request
    from fastapi import HTTPException
    from app.incidents import management_auth
    request = Request({"type":"http", "client":("203.0.113.10", 1234), "headers":[]})
    with pytest.raises(HTTPException) as exc:
        management_auth(request, "Bearer " + TOKEN)
    assert exc.value.status_code == 403
    response = client.options('/api/incidents/events', headers={"Origin":"https://untrusted.example", "Access-Control-Request-Method":"POST"})
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers
    assert client.patch(f"/api/incidents/{row['id']}/status", headers=HEADERS, json={"status":"INVESTIGATING"}).status_code == 200
