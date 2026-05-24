import json
import platform
import re
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
    """Return the complete assertion format guide for test_cases[].assert per language."""
    guides = {
        "python": (
            "Each test_cases[].assert is a Python assert expression:\n"
            "  `assert add(1, 2) == 3`\n"
            "For multi-statement tests, separate with `;`:\n"
            "  `x = add(1, 2); assert x == 3`"
        ),
        "javascript": (
            "The code that runs inside a test function. Use __assert__() to check results:\n"
            '  `__assert__(add(1, 2) === 3, "1+2 should be 3")`\n'
            "__assert__(cond, msg) throws an Error if cond is false. "
            "For multi-step tests, use multiple statements separated by newlines."
        ),
        "typescript": (
            "The code that runs inside a test function. Use __assert__() to check results:\n"
            '  `__assert__(add(1, 2) === 3, "1+2 should be 3")`\n'
            "__assert__(cond, msg) throws an Error if cond is false. "
            "For multi-step tests, use multiple statements separated by newlines."
        ),
        "c": (
            "Each test_cases[].assert is a C expression (it will be wrapped by the test runner):\n"
            "  `add(1, 2) == 3`\n"
            "For strings: `strcmp(result, \"expected\") == 0`"
        ),
        "cpp": (
            "Each test_cases[].assert is a C++ expression (it will be wrapped by the test runner):\n"
            "  `add(1, 2) == 3`\n"
            "For strings: `strcmp(result, \"expected\") == 0`"
        ),
        "bash": (
            "Each test_cases[].assert uses the __test__ function:\n"
            '  `__test__ "test name" "expected output" your_function arg1 arg2`\n'
            "The __test__ function captures stdout and compares it to the expected string."
        ),
    }
    return guides.get(language_name, "Use assert statements")


def _template_example_for(language_name: str) -> str:
    """Return a single template example for the target language only."""
    examples = {
        "python": 'def add(a, b):\n    # TODO: return the sum\n    pass',
        "javascript": 'function add(a, b) {\n  // TODO: return a + b\n}',
        "typescript": 'function add(a: number, b: number): number {\n  // TODO: return a + b\n}',
        "c": 'int add(int a, int b) {\n    /* TODO: return the sum */\n}',
        "cpp": 'int add(int a, int b) {\n    // TODO: return the sum\n}',
        "bash": 'add() {\n  # TODO: return the sum\n  local result=$(( $1 + $2 ))\n  echo "$result"\n}',
    }
    return examples.get(language_name, examples["python"])


def _parse_exercise_json(text: str) -> dict:
    """Parse AI-generated JSON with tolerance for common formatting issues.

    Handles:
    - Invalid JSON escape sequences (\\w, \\s, Windows paths, etc.)
    - Trailing commas before closing brackets/braces
    - Text surrounding the JSON object (markdown, explanations, etc.)
    """
    # Try strict parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract JSON object from surrounding text (find outermost { })
    json_start = text.find("{")
    if json_start != -1:
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

    fixed = text

    # Fix invalid escape sequences: backslash not followed by a valid JSON escape
    # Valid JSON escapes: \"  \\  \/  \b  \f  \n  \r  \t  \uXXXX
    fixed = re.sub(
        r'\\(?![\\"/bfnrt]|u[0-9A-Fa-f]{4})',
        r'\\\\',
        fixed,
    )

    # Fix trailing commas: ,]  ,}
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        logger.warning(
            "Failed to parse exercise JSON after repair: %s. Raw (last 500): %s",
            e, text[-500:],
        )
        raise


async def generate_exercise_async(
    topic_title: str,
    language_name: str,
    section_title: str,
    knowledge_description: str,
    content_language: str = "zh",
    error_feedback: str | None = None,
) -> dict:
    """Generate a coding exercise via AI. Returns parsed JSON dict.

    Set error_feedback to include a previous validation failure so the AI
    can fix syntax/runtime errors in the solution.
    """
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
            template_example=_template_example_for(language_name),
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Generate a coding exercise for section: {section_title}"},
        ]
        if error_feedback:
            messages.append({
                "role": "user",
                "content": (
                    f"The previous solution failed to run with these errors:\n{error_feedback}\n\n"
                    "IMPORTANT: Make sure the 'solution' field contains valid, runnable "
                    f"{language_name} code with NO syntax errors (indentation, missing colons, "
                    "unbalanced brackets, etc.). Verify the code can actually execute."
                ),
            })

        result = await _provider.chat_completion_async(
            model=get_model(),
            messages=messages,
            temperature=AI_GENERATION_TEMPERATURE,
        )
        result = result.strip()
        if result.startswith("```"):
            lines = result.split("\n")
            result = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        parsed = _parse_exercise_json(result)
        elapsed = time.perf_counter() - start
        logger.info("Exercise generated: %d test cases (%.2fs)", len(parsed.get("test_cases", [])), elapsed)
        return parsed
    except Exception:
        elapsed = time.perf_counter() - start
        logger.exception("Exercise generation failed for '%s' (%.2fs)", section_title, elapsed)
        raise
