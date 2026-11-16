"""Offline, exact-digest approval gate. Never reads a path or uploads a file."""
import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.agent_evidence import sanitize


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def approval_digest(bundle):
    # Job IDs vary; approval covers the entire actual incident/evidence/limitations payload.
    return hashlib.sha256(encoded({k: v for k, v in bundle.items() if k != 'investigation_id'})).hexdigest()


class ExportError(ValueError):
    pass


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^E[0-9]{3}$')
    kind: Literal['log', 'source', 'git', 'historical']
    content: str = Field(max_length=65536)
    path: str | None = None
    start_line: int | None = Field(None, ge=1)
    end_line: int | None = Field(None, ge=1)
    sha256: str | None = Field(None, pattern=r'^[0-9a-f]{64}$')
    operation: Literal['status', 'log', 'show', 'diff', 'blame'] | None = None
    commit_sha: str | None = Field(None, pattern=r'^[0-9a-f]{40}$')
    date: str | None = None
    author: str | None = None
    historical_id: str | None = None
    similarity_score: float | None = Field(None, ge=-1, le=1)
    source_ref: str | None = None
    request_id: str | None = None
    event_id: str | None = None


def source_path(value, service):
    path = PurePosixPath(value)
    roots = ('services/shared/', 'services/fixtures/', f'services/{service}/')
    if (str(path) != value or path.is_absolute() or '..' in path.parts or '\\' in value
            or any(p.startswith('.') or p in ('node_modules', '__pycache__') for p in path.parts)
            or path.suffix not in ('.js', '.mjs', '.cjs', '.ts') or not value.startswith(roots)):
        raise ExportError('Unauthorized source path')


def clean_text(value):
    result = sanitize(value)
    result = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+', 'Bearer [REDACTED]', result)
    result = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[EMAIL REDACTED]', result)
    # Reject residual sensitive forms rather than guessing at safe partial disclosure.
    if re.search(r'(?i)\b(?:AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]+|sk-[A-Za-z0-9_-]{8,})\b|-----BEGIN .*PRIVATE KEY|(?:/Users/|/home/|[A-Z]:\\)|\b(?:https?://)[^\s"<>]+|\b(?:\d{1,3}\.){3}\d{1,3}\b|(?:^|[\s/])\.env\b', result):
        raise ExportError('Sensitive or unauthorized content remains after redaction')
    # Unknown credential assignments must never cross the export boundary.
    if re.search(r'(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|authorization)\b\s*["\']?\s*[:=]\s*["\']?(?!\[)([A-Za-z0-9_+/=-]{4,})', result):
        raise ExportError('Credential content is not exportable')
    return result


class EvidenceExportBuilder:
    def __init__(self, approved_synthetic_digests=(), max_bytes=131072):
        self.approved = frozenset(approved_synthetic_digests)
        self.max_bytes = max_bytes

    def build(self, bundle):
        if set(bundle) != {'investigation_id', 'incident_id', 'service_name', 'evidence', 'limitations', 'read_only'} or bundle['read_only'] is not True:
            raise ExportError('Unsupported investigation bundle or permission request')
        # Bound raw data before parsing individual evidence. Approval is an operator assertion
        # of synthetic origin, not a model/client-supplied boolean or inferred property.
        if len(encoded(bundle)) > self.max_bytes:
            raise ExportError('Evidence payload exceeds byte limit')
        digest = approval_digest(bundle)
        if digest not in self.approved:
            raise ExportError('Exact synthetic evidence approval required')
        service = bundle['service_name']
        if service not in ('user-service', 'order-service', 'payment-service'):
            raise ExportError('Unauthorized service')
        if not isinstance(bundle['evidence'], list) or not 1 <= len(bundle['evidence']) <= 70:
            raise ExportError('Evidence count out of bounds')
        if not isinstance(bundle['limitations'], list) or not all(isinstance(x, str) for x in bundle['limitations']):
            raise ExportError('Invalid limitations')
        items, ids = [], set()
        allowed_fields = {
            'log': {'id','kind','content','request_id','event_id'},
            'source': {'id','kind','content','path','start_line','end_line','sha256'},
            'git': {'id','kind','content','operation','commit_sha','date','author','path'},
            'historical': {'id','kind','content','historical_id','similarity_score','source_ref'},
        }
        for raw in bundle['evidence']:
            item = Evidence.model_validate(raw)
            if not set(raw) <= allowed_fields[item.kind] or item.id in ids:
                raise ExportError('Invalid evidence fields or duplicate source identifier')
            ids.add(item.id)
            if item.kind == 'source':
                if item.path is None or item.start_line is None or item.end_line is None or item.sha256 is None or item.end_line < item.start_line:
                    raise ExportError('Source provenance missing')
                source_path(item.path, service)
            if item.kind == 'git':
                if item.operation is None or (item.operation in ('show','diff','log') and item.commit_sha is None):
                    raise ExportError('Git provenance missing')
                if item.path: source_path(item.path, service)
                # Scope every path mentioned by diff/show/blame; never export hidden/env files.
                for path in re.findall(r'(?:services/)[^\s"\']+', item.content):
                    source_path(path.rstrip(':,;)'), service)
            if item.kind == 'historical' and (not item.historical_id or item.similarity_score is None or not item.source_ref):
                raise ExportError('Historical provenance missing')
            entry = item.model_dump(exclude_none=True)
            entry = {k: clean_text(v) if isinstance(v, str) else v for k, v in entry.items()}
            entry['export_sha256'] = hashlib.sha256(entry['content'].encode()).hexdigest()
            items.append(entry)
        result = {'schema_version': 'opsguard.synthetic-export.v1', 'synthetic_approval_sha256': digest,
                  'investigation_id': clean_text(bundle['investigation_id']), 'incident_id': clean_text(bundle['incident_id']),
                  'service_name': service, 'evidence': items, 'limitations': [clean_text(x) for x in bundle['limitations']],
                  'read_only': True}
        payload = encoded(result)
        if len(payload) > self.max_bytes:
            raise ExportError('Sanitized export exceeds byte limit')
        return result
