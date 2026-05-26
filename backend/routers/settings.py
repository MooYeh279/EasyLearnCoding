import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from config import \
    API_KEY_MASK_PREFIX, API_KEY_MASK_SUFFIX, API_KEY_MASK_MIN, \
    AI_API_KEY_DEFAULT, AI_BASE_URL_DEFAULT, AI_MODEL_DEFAULT, \
    WORKSPACE_DIR, AI_HTTP_TIMEOUT, AI_HTTP_CONNECT_TIMEOUT
from database import get_db
from models import AppSetting
from services.ai_service import reload_provider
from logger import get_logger

router = APIRouter(prefix="/api", tags=["settings"])
logger = get_logger("settings")

AI_KEYS = {"ai_api_key", "ai_base_url", "ai_model"}

# ── AI settings ───────────────────────────────────────────────────────

class AiSettingsResponse(BaseModel):
    api_key: str
    base_url: str
    model: str


@router.get("/settings/ai")
def get_ai_settings(db: Session = Depends(get_db)):
    settings = {}
    for row in db.query(AppSetting).filter(AppSetting.key.in_(AI_KEYS)).all():
        settings[row.key] = row.value

    raw_key = settings.get("ai_api_key") or AI_API_KEY_DEFAULT
    masked = raw_key[:API_KEY_MASK_PREFIX] + "****" + raw_key[-API_KEY_MASK_SUFFIX:] \
        if len(raw_key) > API_KEY_MASK_MIN else "****"

    return AiSettingsResponse(
        api_key=masked,
        base_url=settings.get("ai_base_url") or AI_BASE_URL_DEFAULT,
        model=settings.get("ai_model") or AI_MODEL_DEFAULT,
    )


@router.put("/settings/ai")
def update_ai_settings(body: AiSettingsResponse, db: Session = Depends(get_db)):
    api_key = body.api_key
    if "****" in api_key:
        rows = {r.key: r.value for r in db.query(AppSetting).filter(
            AppSetting.key.in_(AI_KEYS)
        ).all()}
        api_key = rows.get("ai_api_key") or AI_API_KEY_DEFAULT

    updates = {
        "ai_api_key": api_key,
        "ai_base_url": body.base_url,
        "ai_model": body.model,
    }
    for key, value in updates.items():
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))
    db.commit()

    reload_provider(api_key, body.base_url, body.model)
    return {"message": "AI settings updated"}


@router.post("/settings/ai/test")
def test_ai_connection(body: AiSettingsResponse):
    """Test AI model connectivity with a simple completion request."""
    from llm.openai_like import OpenAILikeProvider

    api_key = body.api_key
    base_url = body.base_url

    # If key is masked, read real key from DB
    if "****" in api_key:
        from database import SessionLocal
        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == "ai_api_key").first()
            api_key = row.value if row else AI_API_KEY_DEFAULT
        finally:
            db.close()

    start = time.perf_counter()
    try:
        provider = OpenAILikeProvider(api_key=api_key, base_url=base_url)
        result = provider.chat_completion(
            model=body.model,
            messages=[{"role": "user", "content": "Say 'ok' and nothing else."}],
            max_tokens=10,
            temperature=0,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("AI connection test OK: model=%s base_url=%s latency=%sms",
                     body.model, base_url, elapsed_ms)
        return {
            "ok": True,
            "latency_ms": elapsed_ms,
            "model": body.model,
        }
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("AI connection test FAILED: model=%s base_url=%s latency=%sms error=%s",
                       body.model, base_url, elapsed_ms, str(e))
        return {
            "ok": False,
            "latency_ms": elapsed_ms,
            "error": str(e),
        }


# ── Workspace settings ────────────────────────────────────────────────

WORKSPACE_DB_KEY = "learn_code_home"


class WorkspaceResponse(BaseModel):
    path: str


def _read_workspace_from_db(db: Session) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == WORKSPACE_DB_KEY).first()
    return row.value if row else None


@router.get("/settings/workspace")
def get_workspace(db: Session = Depends(get_db)):
    saved = _read_workspace_from_db(db)
    return WorkspaceResponse(path=saved or str(WORKSPACE_DIR))


@router.put("/settings/workspace")
def update_workspace(body: WorkspaceResponse, db: Session = Depends(get_db)):
    from routers.code_executor import set_code_workspace

    # Persist to DB
    row = db.query(AppSetting).filter(AppSetting.key == WORKSPACE_DB_KEY).first()
    if row:
        row.value = body.path
    else:
        db.add(AppSetting(key=WORKSPACE_DB_KEY, value=body.path))
    db.commit()

    # Apply at runtime
    new_workspace = str(Path(body.path) / "workspace")
    Path(new_workspace).mkdir(parents=True, exist_ok=True)
    set_code_workspace(new_workspace)
    return {"message": "Workspace updated", "path": new_workspace}


# ── Search settings ─────────────────────────────────────────────────────

SEARCH_KEYS = {"web_search_provider", "tavily_api_key", "web_search_enabled"}


class SearchSettingsResponse(BaseModel):
    enabled: bool = False
    provider: str = "duckduckgo"
    api_key: str = ""


@router.get("/settings/search")
def get_search_settings(db: Session = Depends(get_db)):
    settings = {}
    for row in db.query(AppSetting).filter(AppSetting.key.in_(SEARCH_KEYS)).all():
        settings[row.key] = row.value

    raw_key = settings.get("tavily_api_key") or ""
    masked = raw_key[:API_KEY_MASK_PREFIX] + "****" + raw_key[-API_KEY_MASK_SUFFIX:] \
        if len(raw_key) > API_KEY_MASK_MIN else "****"

    enabled_val = settings.get("web_search_enabled", "false").lower() == "true"

    return SearchSettingsResponse(
        enabled=enabled_val,
        provider=settings.get("web_search_provider") or "duckduckgo",
        api_key=masked,
    )


@router.put("/settings/search")
def update_search_settings(body: SearchSettingsResponse, db: Session = Depends(get_db)):
    api_key = body.api_key
    if "****" in api_key:
        rows = {r.key: r.value for r in db.query(AppSetting).filter(
            AppSetting.key.in_(SEARCH_KEYS)
        ).all()}
        api_key = rows.get("tavily_api_key") or ""

    updates = {
        "web_search_enabled": "true" if body.enabled else "false",
        "web_search_provider": body.provider,
        "tavily_api_key": api_key,
    }
    for key, value in updates.items():
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))
    db.commit()
    return {"message": "Search settings updated"}
