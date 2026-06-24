from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import application, auto_search, config, jobs, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.auto_search_scheduler import shutdown_scheduler, start_scheduler
    from app.services.auto_search_store import load_config
    cfg = load_config()
    start_scheduler(interval_hours=cfg.interval_hours)
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Job Hunter Assistant",
    description="Agentic career assistant for tech job applications",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "tauri://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(application.router)
app.include_router(config.router)
app.include_router(auto_search.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}
