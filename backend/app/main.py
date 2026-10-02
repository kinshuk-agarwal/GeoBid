import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import tiles, ws
from app.api.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.exceptions import DomainError
from app.realtime.manager import manager as ws_manager
from app.services.auction_worker import run_auction_worker
from app.services.events import event_bus
from app.services.inventory_service import ensure_upcoming_inventory


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # Make sure tomorrow's inventory exists even if the DB was seeded days ago.
    with SessionLocal() as db:
        ensure_upcoming_inventory(db)

    await event_bus.start()
    unsubscribe = event_bus.subscribe(ws_manager.on_event)
    stop = asyncio.Event()
    worker = asyncio.create_task(run_auction_worker(stop)) if settings.auction_worker_enabled else None
    try:
        yield
    finally:
        stop.set()
        if worker:
            await worker
        unsubscribe()
        await event_bus.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        description=(
            "Real-time geospatial digital advertising auction POC. "
            "All footfall values are synthetic."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def _domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message}, headers=headers)

    app.include_router(api_router)
    app.include_router(ws.router)
    app.include_router(tiles.router)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"app": settings.app_name, "version": __version__, "docs": "/docs", "health": "/api/health"}

    return app


app = create_app()
