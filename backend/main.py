import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from config import CORS_ORIGINS, FRONTEND_DIST
from database import engine, Base, SessionLocal
import models  # noqa: F401 — registers all models with Base.metadata
from logger import get_logger

logger = get_logger("api")

app = FastAPI(title="Learn Coding API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info("%s %s → %s (%.2fs)", request.method, request.url.path, response.status_code, elapsed)
    return response


Base.metadata.create_all(bind=engine)

from database import migrate
migrate()


def _recover_stuck_topics():
    """Reset topics stuck in transient states after an unclean shutdown."""
    from models import Topic, TopicStatus, TopicOutline
    db = SessionLocal()
    try:
        stuck_outline = (
            db.query(Topic)
            .filter(Topic.status == TopicStatus.generating_outline)
            .all()
        )
        for topic in stuck_outline:
            has_outline = db.query(TopicOutline).filter(
                TopicOutline.topic_id == topic.id
            ).first()
            topic.status = TopicStatus.outline_ready if has_outline else TopicStatus.draft
            topic.generation_progress = None
            logger.warning("Recovered stuck outline generation: topic_id=%s title=%s", topic.id, topic.title)

        stuck_content = (
            db.query(Topic)
            .filter(Topic.status == TopicStatus.generating_content)
            .all()
        )
        for topic in stuck_content:
            topic.status = TopicStatus.outline_ready
            topic.generation_progress = None
            logger.warning("Recovered stuck content generation: topic_id=%s title=%s", topic.id, topic.title)

        if stuck_outline or stuck_content:
            db.commit()
    finally:
        db.close()


_recover_stuck_topics()

from routers.languages import router as languages_router
from routers.courses import router as courses_router
from routers.topics import router as topics_router
from routers.sections import router as sections_router
from routers.lessons import router as lessons_router
from routers.code_executor import router as code_executor_router
from routers.chat import router as chat_router
from routers.environment import router as environment_router
from routers.settings import router as settings_router
from routers.exercises import router as exercises_router

app.include_router(settings_router)
app.include_router(languages_router)
app.include_router(courses_router)
app.include_router(topics_router)
app.include_router(sections_router)
app.include_router(lessons_router)
app.include_router(code_executor_router)
app.include_router(chat_router)
app.include_router(environment_router)
app.include_router(exercises_router)

@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve built frontend as SPA (when available)
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
