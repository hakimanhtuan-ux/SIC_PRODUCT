from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "FactCheck Assistent – Hệ thống API kiểm chứng thông tin & giám định hình ảnh dựa trên bằng chứng. "
        "Phục vụ đồng thời Web Application và Chrome Browser Extension."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"^(https?|chrome-extension)://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api-info")
async def api_info():
    return {
        "name": "FactCheck Assistent – Evidence-Based Verification Engine",
        "tagline": "Kiểm chứng tại điểm chạm, tin tưởng dựa trên bằng chứng.",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


STATIC_WEB_DIR = Path(__file__).resolve().parents[1] / "static_web"
if STATIC_WEB_DIR.exists() and (STATIC_WEB_DIR / "index.html").exists():
    app.mount(
        "/",
        StaticFiles(directory=str(STATIC_WEB_DIR), html=True),
        name="static_web",
    )
else:
    @app.get("/")
    async def root():
        return {
            "name": "FactCheck Assistent – Evidence-Based Verification Engine",
            "tagline": "Kiểm chứng tại điểm chạm, tin tưởng dựa trên bằng chứng.",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

