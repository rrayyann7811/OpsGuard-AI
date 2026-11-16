"""Validated, attributed historical documents; no operational incident state is copied."""
import hashlib
import json
import re
import unicodedata
from datetime import date
from uuid import NAMESPACE_URL, uuid5
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.incidents import redact, Service, Severity


class HistoricalIncident(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^SYN-(USR|ORD|PAY)-[0-9]{3}$")
    title: str = Field(min_length=3, max_length=200)
    service_name: Service
    symptoms: str = Field(min_length=10, max_length=4000)
    error_type: str = Field(min_length=1, max_length=128)
    error_message: str = Field(min_length=3, max_length=2000)
    root_cause: str = Field(min_length=10, max_length=4000)
    resolution: str = Field(min_length=10, max_length=4000)
    technology: list[str] = Field(min_length=1, max_length=12)
    severity: Severity
    incident_date: date
    source_ref: str = Field(min_length=3, max_length=512)
    runbook: list[str] = Field(min_length=1, max_length=12)
    code_context: str = Field(max_length=2000)
    http_status: int = Field(ge=400, le=599)
    synthetic: Literal[True]

    @field_validator("technology", "runbook")
    @classmethod
    def bounded_items(cls, values):
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError("List entries must be nonempty and bounded")
        return values


def normalize(text):
    return re.sub(r"[ \t]+", " ", unicodedata.normalize("NFKC", redact(text))).strip()


def safe_document(document):
    data = document.model_dump(mode="json")
    for key, value in data.items():
        if isinstance(value, str) and key not in ("id", "service_name", "severity", "incident_date"):
            data[key] = normalize(value)
        elif isinstance(value, list):
            data[key] = [normalize(item) for item in value]
    return data


def prepare(document):
    data = safe_document(document)
    return "\n".join([
        f"{data['title']} | {data['service_name']}",
        f"Error: {data['error_type']} HTTP {data['http_status']}: {data['error_message']}",
        f"Symptoms: {data['symptoms']}", f"Root cause: {data['root_cause']}",
        f"Resolution: {data['resolution']}",
        "Runbook: " + "; ".join(data["runbook"]),
        "Technology: " + ", ".join(data["technology"]),
        "Code context: " + data["code_context"],
    ])


def document_hash(document, model_key):
    canonical = json.dumps(safe_document(document), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((model_key + canonical).encode()).hexdigest()


def point_id(document_id, chunk_index):
    return str(uuid5(NAMESPACE_URL, f"opsguard-history-v1:{document_id}:{chunk_index}"))


def load_dataset(path):
    raw = json.loads(path.read_text())
    if not isinstance(raw, list) or not 1 <= len(raw) <= 1000:
        raise ValueError("Dataset must contain 1–1000 documents")
    documents = [HistoricalIncident.model_validate(item) for item in raw]
    if len({doc.id for doc in documents}) != len(documents):
        raise ValueError("Duplicate historical document IDs")
    return documents
