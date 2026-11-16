from time import perf_counter
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from app.database import get_db
from app.incidents import Service, Severity, find, redact
from app.knowledge_documents import normalize

router = APIRouter(prefix="/api/knowledge", tags=["Historical knowledge"])


def get_store(request: Request):
    store = getattr(request.app.state, "knowledge", None)
    if store is None: raise HTTPException(503, "Knowledge index has not initialized")
    return store


class SearchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top_k: int = Field(3, strict=True, ge=1, le=10)
    service: Service | None = None
    severity: Severity | None = None
    min_score: float = Field(.25, ge=-1, le=1, allow_inf_nan=False)
    ranking: Literal["semantic"] = "semantic"


class SearchInput(SearchOptions):
    query: str = Field(min_length=3, max_length=6000)

    @field_validator("query")
    @classmethod
    def query_text(cls, value):
        if len(value.strip()) < 3: raise ValueError("Query requires three non-whitespace characters")
        return normalize(value)


def run_search(store, query, options):
    started = perf_counter()
    try:
        results = store.search(query, **options.model_dump())
        return {"items":results, "total":len(results), "ranking":options.ranking,
                "duration_ms":round((perf_counter() - started)*1000, 2),
                "notice":"Synthetic historical evidence, not a verified root cause for the current incident."}
    except Exception:
        raise HTTPException(503, "Historical retrieval unavailable. Check the local model and Qdrant configuration.") from None


@router.get("/status")
def status(store=Depends(get_store)):
    return store.status()


@router.get("/incidents")
def documents(page: int=Query(1, ge=1), page_size: int=Query(12, ge=1, le=100), service: Service | None=None, severity: Severity | None=None, store=Depends(get_store)):
    try:
        docs = store.documents(service, severity)
    except Exception:
        raise HTTPException(503, "Knowledge index unavailable") from None
    return {"items":docs[(page-1)*page_size:page*page_size], "total":len(docs), "page":page, "page_size":page_size}


@router.get("/incidents/{document_id}")
def document(document_id: str, store=Depends(get_store)):
    if len(document_id) > 64: raise HTTPException(422, "Invalid historical document ID")
    try:
        docs = [doc for doc in store.documents() if doc["id"] == document_id]
    except Exception:
        raise HTTPException(503, "Knowledge index unavailable") from None
    if not docs: raise HTTPException(404, "Historical incident not found")
    return {"incident":docs[0]}


@router.post("/search")
def search(body: SearchInput, store=Depends(get_store)):
    return run_search(store, body.query, SearchOptions(**body.model_dump(exclude={"query"})))


@router.post("/similar/{incident_id}")
def similar(incident_id: UUID, body: SearchOptions, db: Session=Depends(get_db), store=Depends(get_store)):
    incident = find(db, incident_id)
    evidence = redact("\n".join([incident.service_name, incident.title, incident.error_type,
        incident.error_message, incident.endpoint, str(incident.http_status), (incident.stack_trace or "")[:2000]]))
    result = run_search(store, evidence[:6000], body)
    return {**result, "incident_id":str(incident_id)}
