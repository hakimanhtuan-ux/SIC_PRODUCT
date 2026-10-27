from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
        "TRUECHECK AI – Hệ thống API kiểm chứng thông tin dựa trên bằng chứng (Evidence-Based AI Verification). "
        "Phục vụ đồng thời Web Application và Chrome Browser Extension."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"^chrome-extension://.*|^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "name": "TrueCheck AI – Evidence-Based Verification Engine",
        "tagline": "Kiểm chứng tại điểm chạm, tin tưởng dựa trên bằng chứng.",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

