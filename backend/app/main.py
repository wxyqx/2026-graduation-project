from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import engine

app = FastAPI(title="ATS 招聘管理系统", version="0.1.0")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "up"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "database": "down"})
