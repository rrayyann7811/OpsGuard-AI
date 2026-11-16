"""Real-process integration using only disposable SQLite data and ephemeral loopback ports."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"


def port():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


def wait(url, process):
    for _ in range(200):
        if process.poll() is not None: raise RuntimeError("Child process exited before readiness")
        try:
            with urlopen(url, timeout=1) as response: return json.load(response)
        except OSError: time.sleep(.05)
    raise RuntimeError("Readiness timeout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discard-evidence', action='store_true',
                        help='Explicitly remove only this run’s disposable evidence after completion')
    args = parser.parse_args()
    processes = []
    directory = tempfile.mkdtemp(prefix="opsguard-pipeline-")
    Path(directory).chmod(0o700)
    print("Isolated evidence retained at: " + directory, flush=True)
    try:
        backend_port, payment_port, user_port, order_port = port(), port(), port(), port()
        api = f"http://127.0.0.1:{backend_port}"
        payment = f"http://127.0.0.1:{payment_port}"
        db = Path(directory) / "incidents.db"
        token = secrets.token_urlsafe(32)
        backend_env = {**os.environ, "DATABASE_URL": "sqlite:///" + str(db), "INCIDENT_WEBHOOK_TOKEN": token,
            "AGENT_EXECUTION_ENABLED": "false", "AGENT_MANAGED_ENABLED": "false",
            "AGENT_MANAGED_HTTP_ENABLED": "false", "ENABLE_INCIDENT_MANAGEMENT": "false",
            "QDRANT_URL": "", "QDRANT_PATH": str(Path(directory)/"qdrant"),
            "USER_SERVICE_URL": f"http://127.0.0.1:{user_port}", "ORDER_SERVICE_URL": f"http://127.0.0.1:{order_port}",
            "PAYMENT_SERVICE_URL": payment, "MONITOR_INTERVAL_SECONDS": "0.2", "MONITOR_TIMEOUT_SECONDS": "0.1"}
        def backend():
            child = subprocess.Popen([str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)], cwd=ROOT/"backend", env=backend_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            processes.append(child)
            wait(api + "/api/health", child)
            return child
        try:
            for name, service_port in (("user-service", user_port), ("order-service", order_port)):
                service = subprocess.Popen(["node", name+"/index.js"], cwd=ROOT/"services", env={
                    **os.environ, "NODE_ENV": "development", "ENABLE_FAULT_INJECTION": "false",
                    "HOST": "127.0.0.1", "PORT": str(service_port), "USER_SERVICE_URL": "",
                    "ORDER_SERVICE_URL": "", "INCIDENT_INGESTION_URL": "", "INCIDENT_WEBHOOK_TOKEN": "",
                }, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(service)
                wait(f"http://127.0.0.1:{service_port}/health", service)
            server = backend()
            subprocess.run([str(PYTHON), str(ROOT/"scripts/check-health.py"), api], check=True)
            with (Path(directory)/"payment.jsonl").open("w+") as logs:
                payment_env = {**os.environ,
                    "NODE_ENV":"development", "ENABLE_FAULT_INJECTION":"true", "HOST":"127.0.0.1", "PORT":str(payment_port),
                    "ORDER_SERVICE_URL":"", "INCIDENT_INGESTION_URL":api+"/api/incidents/events", "INCIDENT_WEBHOOK_TOKEN":token}
                def start_payment():
                    process = subprocess.Popen(["node", "payment-service/index.js"], cwd=ROOT/"services",
                        env=payment_env, stdout=logs, stderr=subprocess.STDOUT)
                    processes.append(process)
                    wait(payment+"/health", process)
                    return process
                child = start_payment()
                def health_until(predicate):
                    for _ in range(300):
                        with urlopen(api+"/api/services", timeout=2) as response:
                            states = json.load(response)["items"]
                        if predicate(states): return states
                        time.sleep(.02)
                    raise AssertionError("Service health did not reach expected state")
                health_until(lambda rows: all(row["status"] == "Healthy" for row in rows))
                env = {**os.environ, "NEXT_PUBLIC_API_URL":api, "OPSGUARD_LIVE_PAYMENT_URL":payment}
                subprocess.run(["npm", "test", "--", "integration/live-pipeline.test.tsx"], cwd=ROOT/"frontend", env=env, check=True)
                child.terminate(); child.wait(timeout=10)
                health_until(lambda rows: any(row["service_name"] == "payment-service" and row["status"] == "Degraded" for row in rows))
                outage = health_until(lambda rows: any(row["service_name"] == "payment-service" and row["status"] == "Unavailable" and row["consecutive_failures"] >= 3 for row in rows))
                child = start_payment()
                recovery = health_until(lambda rows: all(row["status"] == "Healthy" and row["consecutive_failures"] == 0 for row in rows))
                logs.flush(); logs.seek(0)
                evidence = logs.read()
                assert '"event":"incident"' in evidence or '"event": "incident"' in evidence
                assert token not in evidence
                assert "PublicationFailure" not in evidence
            with sqlite3.connect(db) as connection:
                assert connection.execute("select count(*) from incidents").fetchone()[0] == 1
                assert connection.execute("select occurrence_count from incidents").fetchone()[0] == 2
                assert connection.execute("select count(*) from incident_events").fetchone()[0] == 2
            server.terminate(); server.wait(timeout=10)
            server = backend()
            with urlopen(api+"/api/incidents") as response:
                persisted = json.load(response)
                assert persisted["total"] == 1 and persisted["items"][0]["occurrence_count"] == 2
            with urlopen(api+"/api/incidents/summary") as response:
                summary = json.load(response)
                assert summary["total"] == 1 and summary["active"] == 1
                assert sum(day["events"] for day in summary["history"]) == 2
            with urlopen(api+"/api/incidents/"+persisted["items"][0]["id"]+"/events") as response:
                events = json.load(response)
                assert events["total"] == 2
            records = [json.loads(line) for line in evidence.splitlines() if line.strip().startswith('{')]
            incident_records = [record for record in records if record.get("event") == "incident"]
            assert len(incident_records) == 2
            Path(directory, "verification.json").write_text(json.dumps({
                "synthetic_demo": True, "incident_count": 1, "occurrence_count": 2,
                "restart_persistence": True, "summary": summary,
                "incident": persisted["items"][0], "events": events["items"],
                "structured_incident_records": len(incident_records),
                "ai_execution_enabled": False, "secrets_in_logs": False,
                "outage": outage, "recovery": recovery,
                "health_failures_created_incidents": False,
            }, indent=2))
            print("PASS: real Node failure -> authenticated FastAPI -> SQLite -> React live list/details/service health; dedup count 2; API restart persistence; three healthy services, payment degraded/unavailable/recovered; no secret in logs")
        finally:
            for child in reversed(processes):
                if child.poll() is None:
                    child.terminate()
                    try: child.wait(timeout=10)
                    except subprocess.TimeoutExpired: child.kill(); child.wait()

    finally:
        if args.discard_evidence:
            import shutil
            shutil.rmtree(directory)
        else:
            print("Evidence preserved for owner review: " + directory)


if __name__ == "__main__": main()
