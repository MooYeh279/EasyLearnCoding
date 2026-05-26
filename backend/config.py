import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # project root (learn-coding/)
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

WORKSPACE_DIR = Path(os.getenv("LEARN_CODE_HOME", Path.home() / ".learn-code"))
DATA_DIR = WORKSPACE_DIR / "data"
CODE_WORKSPACE = WORKSPACE_DIR / "workspace"

for _d in (DATA_DIR, CODE_WORKSPACE):
    _d.mkdir(parents=True, exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'learn.db'}")

# ── AI defaults (used only when DB has no saved settings) ────────────
AI_API_KEY_DEFAULT = "sk-placeholder"
AI_BASE_URL_DEFAULT = "https://api.openai.com/v1"
AI_MODEL_DEFAULT = "gpt-4o"

# ── Code execution ────────────────────────────────────────────────────
CODE_TIMEOUT = 10          # seconds, interpreter/run timeout
CODE_COMPILE_TIMEOUT = 15  # seconds, C/C++ compilation timeout
CODE_MAX_LENGTH = 100_000  # max chars per code snippet
CODE_QUEUE_POLL = 0.1      # seconds, SSE queue poll interval
CODE_C_RUN_TIMEOUT = 10    # seconds, compiled C/C++ binary run timeout

# ── AI / Chat ─────────────────────────────────────────────────────────
CHAT_CONTENT_MAX_CHARS = 4000    # lesson content truncated to this in prompt
CHAT_HISTORY_MAX = 20            # last N messages included as context
CHAT_TEMPERATURE = 0.7
AI_GENERATION_TEMPERATURE = 0.7
AI_HTTP_TIMEOUT = 300            # seconds, LLM provider HTTP read timeout
AI_HTTP_CONNECT_TIMEOUT = 10   # seconds, LLM provider HTTP connect timeout
AI_MAX_CONCURRENCY = 3           # max parallel lesson generation calls

# ── API key masking ───────────────────────────────────────────────────
API_KEY_MASK_PREFIX = 6
API_KEY_MASK_SUFFIX = 4
API_KEY_MASK_MIN = 10

# ── Logging ───────────────────────────────────────────────────────────
LOG_BACKUP_COUNT = 7
LOG_ROTATION_INTERVAL = 1  # days

# ── CORS ──────────────────────────────────────────────────────────────
CORS_ORIGINS = ["http://localhost:5173"]

# ── Environment check ─────────────────────────────────────────────────
ENV_CHECK_TIMEOUT = 5     # seconds, subprocess timeout per component
ENV_CHECK_CACHE_TTL = 300  # seconds, in-memory cache TTL

# ── Outline / Lesson cell IDs ─────────────────────────────────────────
CELL_ID_LENGTH = 8  # chars, truncated UUID hex for notebook cell ids
