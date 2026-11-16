"""Create a new disposable demo workspace. Never changes an existing database."""
from pathlib import Path
import json
import secrets
import shlex

root = Path(__file__).resolve().parents[1]
name = "phase3-" + secrets.token_hex(6)
folder = root / "backend/.demo" / name
folder.mkdir(parents=True, mode=0o700)
marker = folder / ".opsguard-disposable"
marker.write_text(json.dumps({"disposable": True, "name": name}))
values = {
    "DATABASE_URL": "sqlite:///" + str(folder / "incidents.db"),
    "INCIDENT_WEBHOOK_TOKEN": secrets.token_urlsafe(32),
    "INCIDENT_INGESTION_URL": "http://127.0.0.1:8000/api/incidents/events",
    "NODE_ENV": "development", "ENABLE_FAULT_INJECTION": "true",
    "ENVIRONMENT": "development", "ENABLE_INCIDENT_MANAGEMENT": "false",
    "AGENT_EXECUTION_ENABLED": "false", "AGENT_MANAGED_ENABLED": "false",
    "AGENT_MANAGED_HTTP_ENABLED": "false",
    "QDRANT_URL": "", "QDRANT_PATH": str(folder / "qdrant"),
}
env = folder / "environment.sh"
env.write_text("\n".join("export " + key + "=" + shlex.quote(value) for key, value in values.items()) + "\n")
env.chmod(0o600)
print("Disposable demo: " + name)
print("In BOTH backend and payment terminals run:")
print("source " + shlex.quote(str(env)))
print("Secrets are stored only in that private environment file. Do not commit it.")
