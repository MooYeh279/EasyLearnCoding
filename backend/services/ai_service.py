from __future__ import annotations

import json
import platform
import re
import time
from typing import AsyncGenerator
from config import AI_API_KEY_DEFAULT, AI_BASE_URL_DEFAULT, AI_MODEL_DEFAULT, \
    AI_GENERATION_TEMPERATURE, PROMPTS_DIR
from logger import get_logger
from llm import LLMProvider, OpenAILikeProvider
from services.agent_loop import agent_loop

logger = get_logger("ai")

_TOOL_GUIDANCE = (
    "\n\n## Available Tools\n"
    "You have access to the following tools:\n"
    "- `web_search(query)`: Search the web for current information, documentation, "
    "or factual questions. Use this when you need up-to-date information or "
    "when the topic is outside your knowledge cutoff.\n"
    "- `web_fetch(url)`: Fetch and read the content of a specific URL. "
    "Use this after `web_search` to read a page you found.\n\n"
    "Guidelines:\n"
    "- Only use tools when you genuinely need external information.\n"
    "- If you already know the answer, generate content directly without calling tools.\n"
    "- After 2-3 searches, synthesize what you have and produce output.\n"
    "- Do NOT search if you are confident in your knowledge of the topic.\n\n"
    "## Citation Rules (CRITICAL)\n"
    "EVERY fact, concept, or code pattern you learned from a web search/fetch "
    "MUST have a numbered citation marker in the body text WHERE that information "
    "appears. This is NOT optional — the student must be able to trace every piece "
    "of sourced information back to its origin.\n\n"
    "Correct format in body text (inline markers in every paragraph that uses sourced info):\n"
    "  Python 3.12 引入了新的类型参数语法 [1]，这使得泛型代码更加简洁。\n"
    "  根据 PEP 695 规范 [2]，新语法支持...\n\n"
    "At the end of the lesson, add a \"## 参考来源\" section:\n"
    "  [1] https://docs.python.org/3/whatsnew/3.12.html - Python 3.12 新特性\n"
    "  [2] https://peps.python.org/pep-0695/ - PEP 695 类型参数语法\n\n"
    "If no external sources were used, omit the references section entirely.\n"
    "CRITICAL: Every [N] in the references section MUST appear at least once in the body.\n"
)

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


def _build_outline_messages(topic_title: str, language_name: str, content_language: str,
                            previous_outline: dict | None = None, feedback: str | None = None) -> list[dict]:
    content_lang_name = _lang_name(content_language)
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
            "content": (
                f"Previous outline:\n{json.dumps(previous_outline, ensure_ascii=False, indent=2)}\n\n"
                f"User feedback: {feedback}\n\nPlease regenerate the outline based on this feedback."
            ),
        })
    else:
        messages.append({"role": "user", "content": f"Generate a learning outline for: {topic_title}"})
    return messages


async def generate_outline_stream_async(
    topic_title: str, language_name: str, content_language: str = "zh",
    previous_outline: dict | None = None, feedback: str | None = None,
    enable_tools: bool = False,
) -> AsyncGenerator[dict, None]:
    """Generate outline via agent loop, yielding SSE events."""
    messages = _build_outline_messages(
        topic_title, language_name, content_language, previous_outline, feedback)
    if enable_tools and messages:
        messages[0]["content"] += _TOOL_GUIDANCE
    async for event in agent_loop(messages, get_model(), get_provider(),
                                  enable_tools=enable_tools):
        yield event


async def generate_lesson_stream_async(
    topic_title: str, language_name: str, section_title: str,
    lesson_title: str, content_language: str = "zh",
    enable_tools: bool = False,
) -> AsyncGenerator[dict, None]:
    """Generate lesson content via agent loop, yielding SSE events."""
    messages = _build_lesson_messages(
        topic_title, language_name, section_title, lesson_title, content_language)
    if enable_tools and messages:
        messages[0]["content"] += _TOOL_GUIDANCE
    async for event in agent_loop(messages, get_model(), get_provider(),
                                  enable_tools=enable_tools):
        yield event



def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) if lines[-1].strip() != "```" else len(lines) - 1
        text = "\n".join(lines[start:end])
    return text


def _extract_and_repair_json(text: str) -> str:
    """Extract JSON object from surrounding text and repair common issues."""
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    json_start = text.find("{")
    if json_start == -1:
        return text

    depth = 0
    in_string = False
    escape = False
    json_end = -1
    for i in range(json_start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
        elif ch == '"' and not escape:
            in_string = not in_string
        elif not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_end = i + 1
                    break
    if json_end != -1:
        text = text[json_start:json_end]

    fixed = re.sub(
        r'\\(?![\\"/bfnrt]|u[0-9A-Fa-f]{4})',
        r'\\\\',
        text,
    )
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
    return fixed


def parse_exercise_output(raw_text: str) -> RawExerciseOutput:
    """Parse and validate AI output into RawExerciseOutput.

    Strips markdown fences, extracts JSON, repairs common issues,
    then validates with Pydantic. Raises on unrecoverable errors.
    """
    from services.exercise_schema import RawExerciseOutput

    text = _strip_markdown_fences(raw_text)
    repaired = _extract_and_repair_json(text)

    try:
        parsed = json.loads(repaired)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse exercise JSON after repair: %s", e)
        raise

    return RawExerciseOutput.model_validate(parsed)


async def generate_exercise_async(
    topic_title: str,
    language_name: str,
    section_title: str,
    knowledge_description: str,
    content_language: str = "zh",
    error_feedback: str | None = None,
) -> RawExerciseOutput:
    """Generate a coding exercise via AI. Returns validated RawExerciseOutput.

    Set error_feedback to include a previous validation failure so the AI
    can fix syntax/runtime errors in the solution.
    """
    from services.exercise_schema import RawExerciseOutput

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
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Generate a coding exercise for section: {section_title}"},
        ]
        if error_feedback:
            messages.append({
                "role": "user",
                "content": (
                    f"The previous exercise had these errors:\n{error_feedback}\n\n"
                    "IMPORTANT: Make sure the 'solution' field contains valid, runnable "
                    f"{language_name} code with NO syntax errors. "
                    "Verify the code can actually execute."
                ),
            })

        result = await _provider.chat_completion_async(
            model=get_model(),
            messages=messages,
            temperature=AI_GENERATION_TEMPERATURE,
        )
        exercise = parse_exercise_output(result)
        elapsed = time.perf_counter() - start
        logger.info(
            "Exercise generated: %d test cases (%.2fs)",
            len(exercise.test_cases), elapsed,
        )
        return exercise
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("Exercise generation failed for '%s' (%.2fs)", section_title, elapsed)
        raise
