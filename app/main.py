from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import traceback

from app.routes import router

app = FastAPI(title="Vendor Contract Automation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/health")
def health():
    url = os.getenv("DATABASE_URL") or ""
    result = {
        "status": "ok",
        "has_db_url": bool(url),
        "db_url_length": len(url),
        "db_host_part": "",
        "db_error": None,
    }
    # 打印 host 部分（@ 后、: 前），不含密码
    try:
        if "@" in url:
            after_at = url.split("@", 1)[1]
            result["db_host_part"] = after_at.split("/")[0]
    except Exception:
        pass

    # 真实尝试连接
    try:
        import psycopg2
        conn = psycopg2.connect(url)
        conn.close()
        result["db_error"] = "CONNECT_OK"
    except Exception as e:
        result["db_error"] = f"{type(e).__name__}: {e}"
        result["traceback_tail"] = traceback.format_exc().splitlines()[-5:]
    return result