import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from app.database import Base
from app.incidents import router
from app.monitor import ServiceMonitor
from app.security import BodyLimit
from app.knowledge_store import KnowledgeStore
from app.knowledge_api import router as knowledge_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.config import get_settings
from app.database import engine
from sqlalchemy.orm import sessionmaker
from app.investigations import router as investigation_router
from app.investigation_worker import InvestigationManager

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    app.state.knowledge = KnowledgeStore(settings)
    app.state.monitor = ServiceMonitor(settings)
    app.state.investigations = InvestigationManager(settings, sessionmaker(bind=engine), app.state.knowledge)
    app.state.investigations.start()
    task = asyncio.create_task(app.state.monitor.run()) if settings.monitor_enabled else None
    try:
        yield
    finally:
        await app.state.investigations.stop()
        try:
            app.state.knowledge.close()
        except Exception:
            logger.warning("Knowledge index close failed")
        app.state.monitor.stop()
        if task:
            await task


app = FastAPI(title=settings.app_name, version="0.1.0", description="Persistent incident monitoring, historical retrieval and read-only investigation orchestration.", lifespan=lifespan)
app.include_router(router)
app.include_router(knowledge_router)
app.include_router(investigation_router)
app.add_middleware(BodyLimit)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "PATCH", "POST"], allow_headers=["Accept", "Content-Type", "Authorization"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: str


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})
    return HealthResponse(status="healthy", service=settings.app_name, version="0.1.0", environment=settings.environment, database="connected")


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.error("Unhandled API error on %s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]})
