from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import application, config, design, jobs, profile

app = FastAPI(
    title="Job Hunter Assistant",
    description="Agentic career assistant for tech job applications",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(application.router)
app.include_router(config.router)
app.include_router(design.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}
