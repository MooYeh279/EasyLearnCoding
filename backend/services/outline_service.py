import json
import os
import platform
import re
import subprocess
import tempfile
import uuid
from sqlalchemy.orm import Session
from models import Topic, TopicOutline, Section, TopicStatus
from logger import get_logger
from config import CELL_ID_LENGTH

logger = get_logger("outline")

_IS_WIN = platform.system() == "Windows"

# Languages that produce runnable code cells (not display-only blocks)
_CODE_LANGUAGES = {"python", "javascript", "typescript", "bash", "shell", "c", "cpp", "cmd", "powershell", "bat", "ps1"}

# ── Syntax validation ────────────────────────────────────────────────────

def _validate_syntax(language: str, code: str) -> bool:
    """Check whether *code* is syntactically valid in *language*.

    Returns True if syntax is valid, False otherwise.
    Uses lightweight checks (AST parse for Python, --check for node/bash,
    -fsyntax-only for C/C++).
    """
    code = code.strip()
    if not code:
        return False

    try:
        if language == "python":
            compile(code, "<string>", "exec")
            return True
        elif language in ("javascript", "typescript"):
            return _check_node_syntax(code, language)
        elif language in ("bash", "shell"):
            return _check_bash_syntax(code)
        elif language == "c":
            return _check_gcc_syntax(code, "c")
        elif language == "cpp":
            return _check_gcc_syntax(code, "c++")
        elif language in ("powershell", "ps1"):
            return _check_powershell_syntax(code)
        elif language in ("cmd", "bat"):
            return True
        else:
            return True
    except Exception:
        return False


def _check_node_syntax(code: str, language: str) -> bool:
    """Check JS syntax via node --check, TS via tsc --noEmit."""
    if language == "typescript":
        return _check_tsc_syntax(code)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["node", "--check", tmp_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=10, shell=_IS_WIN,
            )
            return result.returncode == 0
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True


def _check_tsc_syntax(code: str) -> bool:
    """Check TypeScript syntax via tsc --noEmit."""
    import shutil
    if not shutil.which("tsc") and not shutil.which("npx"):
        return True
    try:
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, "check.ts")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit", tmp_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=30,
                shell=_IS_WIN, cwd=tmp_dir,
            )
            return result.returncode == 0
        finally:
            try:
                os.unlink(tmp_path)
                os.rmdir(tmp_dir)
            except OSError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True


def _check_bash_syntax(code: str) -> bool:
    """Check bash syntax via bash -n."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["bash", "-n", tmp_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=10, shell=_IS_WIN,
            )
            return result.returncode == 0
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True


def _check_powershell_syntax(code: str) -> bool:
    """Check PowerShell syntax via AST parser (ParseInput)."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = os.path.abspath(f.name).replace("\\", "/")
        try:
            check_script = (
                "$code = Get-Content -LiteralPath '"
                + tmp_path
                + "' -Raw; "
                "$parseErrors = $null; "
                "$null = [System.Management.Automation.Language.Parser]::ParseInput("
                "$code, [ref]$null, [ref]$parseErrors); "
                "exit $parseErrors.Count"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", check_script],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15, shell=_IS_WIN,
            )
            return result.returncode == 0
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True


def _check_gcc_syntax(code: str, lang: str) -> bool:
    """Check C/C++ syntax via gcc/g++ -fsyntax-only."""
    ext = ".cpp" if lang == "c++" else ".c"
    compiler = "g++" if lang == "c++" else "gcc"
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name
        try:
            result = subprocess.run(
                [compiler, "-fsyntax-only", tmp_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15, shell=_IS_WIN,
            )
            return result.returncode == 0
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return True

def _markdown_to_cells(md: str, default_language: str = "python") -> str:
    """Convert AI-generated Markdown into a JSON cell array for notebook rendering.

    Rules:
    - Real language tag (python, js, c, etc.)  → runnable code cell
    - ``txt`` tag or bare ``` (no tag) → plaintext code cell (display, not runnable)
    - Unrecognized language → plaintext code cell
    - Text outside code fences → markdown cells
    """
    cells = []

    # Split on lines that are exactly ``` (opening or closing fence)
    blocks = re.split(r'^```', md, flags=re.MULTILINE)

    for i, block in enumerate(blocks):
        if not block.strip():
            continue
        if i % 2 == 0:
            cells.append({
                "id": uuid.uuid4().hex[:CELL_ID_LENGTH],
                "type": "markdown",
                "content": block.strip(),
            })
        else:
            first_newline = block.find("\n")
            if first_newline == -1:
                lang = block.strip()
                code = ""
            else:
                lang = block[:first_newline].strip()
                code = block[first_newline + 1:].strip()

            if not code:
                continue

            normalized_lang = lang.lower()
            if normalized_lang in _CODE_LANGUAGES and _validate_syntax(normalized_lang, code):
                cells.append({
                    "id": uuid.uuid4().hex[:CELL_ID_LENGTH],
                    "type": "code",
                    "language": normalized_lang,
                    "code": code,
                    "output": None,
                })
            else:
                # Syntax invalid or unrecognized — keep as markdown with original fences
                fence = "```" + (lang if lang else "") + "\n" + code + "\n```"
                cells.append({
                    "id": uuid.uuid4().hex[:CELL_ID_LENGTH],
                    "type": "markdown",
                    "content": fence,
                })

    return json.dumps(cells, ensure_ascii=False)


def save_outline(db: Session, topic_id: int, outline_data: dict, feedback: str = None):
    existing = db.query(TopicOutline).filter(TopicOutline.topic_id == topic_id).first()
    history = []
    if existing and existing.sections_json:
        history = (existing.feedback_history or []).copy()
        history.append({
            "previous_outline": existing.sections_json,
        })
    if feedback:
        if history:
            history[-1]["feedback"] = feedback

    if existing:
        existing.sections_json = outline_data
        existing.feedback_history = history
        saved = existing
    else:
        saved = TopicOutline(
            topic_id=topic_id,
            sections_json=outline_data,
            feedback_history=history,
        )
        db.add(saved)

    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic:
        topic.status = TopicStatus.outline_ready
    db.commit()
    db.refresh(saved)
    return saved
