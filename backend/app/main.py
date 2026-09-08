from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import engine
from app.routers import ai_configs, ai_screen, applications, auth, candidates, export, positions, stats

app = FastAPI(title="ATS 招聘管理系统", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Row-Count"],
)

for r in (auth, positions, candidates, applications, ai_configs, ai_screen, stats, export):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "up"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "database": "down"})
