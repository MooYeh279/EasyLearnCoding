import json
import platform
import time
from config import AI_API_KEY_DEFAULT, AI_BASE_URL_DEFAULT, AI_MODEL_DEFAULT, \
    PROMPTS_DIR, AI_GENERATION_TEMPERATURE
from logger import get_logger
from llm import LLMProvider, OpenAILikeProvider

logger = get_logger("ai")

_current_model = AI_MODEL_DEFAULT
_provider: LLMProvider | None = None


def _read_db_settings():
    """Read AI settings from DB, falling back to built-in defaults."""
    from database import SessionLocal
    from models import AppSetting
    db = SessionLocal()
    try:
        rows = {r.key: r.value for r in db.query(AppSetting).filter(
            AppSetting.key.in_({"ai_api_key", "ai_base_url", "ai_model"})
        ).all()}
    finally:
        db.close()
    return (
        rows.get("ai_api_key") or AI_API_KEY_DEFAULT,
        rows.get("ai_base_url") or AI_BASE_URL_DEFAULT,
        rows.get("ai_model") or AI_MODEL_DEFAULT,
    )


def _init_provider():
    global _provider, _current_model
    key, url, model = _read_db_settings()
    _current_model = model
    _provider = OpenAILikeProvider(api_key=key, base_url=url)


_init_provider()


def get_provider() -> LLMProvider:
    assert _provider is not None
    return _provider


def get_model() -> str:
    return _current_model


def set_provider(provider: LLMProvider) -> None:
    global _provider
    _provider = provider


def reload_provider(api_key: str, base_url: str, model: str | None = None) -> None:
    global _provider, _current_model
    _provider = OpenAILikeProvider(api_key=api_key, base_url=base_url)
    if model is not None:
        _current_model = model


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt file not found: {path}")


def _lang_name(code: str) -> str:
    return "Chinese (中文)" if code == "zh" else "English"


def get_platform_info() -> str:
    """Return a concise platform description for AI prompts.

    Tells the AI what OS and shell the student is using, so it can generate
    correct command-line examples and code that actually runs.
    """
    system = platform.system()
    if system == "Windows":
        return (
            "Windows — runnable code blocks must use cmd syntax for ```bat / ```cmd "
            "(commands: dir, type, echo, set, etc.) or powershell syntax for "
            "```powershell / ```ps1 (commands: Get-ChildItem, Write-Output, etc.). "
            "NO bash/sh/Unix commands available. Paths use backslashes (C:\\\\Users\\...)."
        )
    elif system == "Darwin":
        return "macOS — Unix environment, bash/zsh available, paths like /Users/..."
    else:
        return "Linux — Unix environment, bash available, paths like /home/..."


def _build_lesson_messages(topic_title: str, language_name: str, section_title: str,
                           lesson_title: str, content_language: str):
    content_lang_name = _lang_name(content_language)
    prompt = _load_prompt("generate_lesson.txt").format(
        language_name=language_name,
        content_language=content_lang_name,
        platform_info=get_platform_info(),
        topic_title=topic_title,
        section_title=section_title,
        lesson_title=lesson_title,
    )
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Write the lesson: {lesson_title}"},
    ]


async def generate_outline_async(topic_title: str, language_name: str, previous_outline: dict | None = None,
                           feedback: str | None = None, content_language: str = "zh") -> dict:
    content_lang_name = _lang_name(content_language)
    logger.info("Generating outline for '%s' (%s) in %s, feedback=%s",
                topic_title, language_name, content_language, bool(feedback))
    start = time.perf_counter()
    try:
        prompt = _load_prompt("generate_outline.txt").format(
            topic_title=topic_title,
            language_name=language_name,
            content_language=content_lang_name,
            platform_info=get_platform_info(),
        )
        messages = [{"role": "system", "content": prompt}]

        if previous_outline and feedback:
            messages.append({
                "role": "user",
                "content": f"Previous outline:\n{json.dumps(previous_outline, ensure_ascii=False, indent=2)}\n\nUser feedback: {feedback}\n\nPlease regenerate the outline based on this feedback."
            })
        else:
            messages.append({"role": "user", "content": f"Generate a learning outline for: {topic_title}"})

        result = await _provider.chat_completion_async(
            model=get_model(),
            messages=messages,
            temperature=AI_GENERATION_TEMPERATURE,
        )
        parsed = json.loads(result)
        elapsed = time.perf_counter() - start
        sections_count = len(parsed.get("sections", []))
        logger.info("Outline generated: %d sections (%.2fs)", sections_count, elapsed)
        return parsed
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("Outline generation failed for '%s' (%.2fs)", topic_title, elapsed)
        raise


async def generate_lesson_async(topic_title: str, language_name: str, section_title: str,
                                 lesson_title: str, content_language: str = "zh") -> str:
    logger.info("Generating lesson async '%s/%s' (%s) in %s",
                section_title, lesson_title, language_name, content_language)
    start = time.perf_counter()
    try:
        messages = _build_lesson_messages(
            topic_title, language_name, section_title, lesson_title, content_language)
        result = await _provider.chat_completion_async(
            model=get_model(),
            messages=messages,
            temperature=AI_GENERATION_TEMPERATURE,
        )
        elapsed = time.perf_counter() - start
        logger.info("Lesson generated async: %d chars (%.2fs)", len(result), elapsed)
        return result
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("Lesson generation async failed for '%s/%s' (%.2fs)",
                         section_title, lesson_title, elapsed)
        raise


def _assertion_syntax_for(language_name: str) -> str:
    """Return language-specific assertion syntax guide for the AI prompt."""
    guides = {
        "python": "Use Python `assert` statements, e.g. `assert add(1, 2) == 3`",
        "javascript": "Use `console.assert()` expressions, e.g. `console.assert(add(1, 2) === 3)`",
        "typescript": "Use `console.assert()` expressions, e.g. `console.assert(add(1, 2) === 3)`",
        "c": "Use C expressions (will be wrapped in CHECK macro), e.g. `add(1, 2) == 3`",
        "cpp": "Use C++ expressions (will be wrapped in CHECK macro), e.g. `add(1, 2) == 3`",
        "bash": 'Use __test__ calls, e.g. `__test__ "1+2" "3" add 1 2`',
    }
    return guides.get(language_name, "Use assert statements")


async def generate_exercise_async(
    topic_title: str,
    language_name: str,
    section_title: str,
    knowledge_description: str,
    content_language: str = "zh",
) -> dict:
    """Generate a coding exercise via AI. Returns parsed JSON dict."""
    content_lang_name = _lang_name(content_language)
    logger.info(
        "Generating exercise for '%s/%s' (%s) in %s",
        section_title, topic_title, language_name, content_language,
    )
    start = time.perf_counter()
    try:
        prompt = _load_prompt("generate_exercise.txt").format(
            language_name=language_name,
            topic_title=topic_title,
            section_title=section_title,
            knowledge_description=knowledge_description,
            content_language=content_lang_name,
            platform_info=get_platform_info(),
            assertion_syntax=_assertion_syntax_for(language_name),
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Generate a coding exercise for section: {section_title}"},
        ]
        result = await _provider.chat_completion_async(
            model=get_model(),
            messages=messages,
            temperature=AI_GENERATION_TEMPERATURE,
        )
        # Strip markdown code fences if present
        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        parsed = json.loads(result)
        elapsed = time.perf_counter() - start
        logger.info("Exercise generated: %d test cases (%.2fs)", len(parsed.get("test_cases", [])), elapsed)
        return parsed
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("Exercise generation failed for '%s' (%.2fs)", section_title, elapsed)
        raise
