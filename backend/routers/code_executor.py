import json
import platform
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from http import HTTPStatus
from pydantic import BaseModel

import os as _os

from config import \
    CODE_TIMEOUT, CODE_COMPILE_TIMEOUT, CODE_MAX_LENGTH, CODE_QUEUE_POLL, \
    CODE_C_RUN_TIMEOUT, CODE_WORKSPACE
from logger import get_logger

_log = get_logger("code_executor")

router = APIRouter(prefix="/api", tags=["code_executor"])

_IS_WIN = platform.system() == "Windows"
_EXE_SUFFIX = ".exe" if _IS_WIN else ""
_PYTHON = "python" if _IS_WIN else "python3"

_workspace = str(CODE_WORKSPACE)


def _restore_workspace():
    """Restore saved workspace path from DB on startup."""
    global _workspace
    try:
        from database import SessionLocal
        from models import AppSetting
        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == "learn_code_home").first()
            if row and row.value:
                saved = str(Path(row.value) / "workspace")
                Path(saved).mkdir(parents=True, exist_ok=True)
                _workspace = saved
        finally:
            db.close()
    except Exception:
        _log.warning("Failed to restore workspace from DB, using default")


_restore_workspace()


def get_code_workspace() -> str:
    return _workspace


def set_code_workspace(path: str) -> None:
    global _workspace
    Path(path).mkdir(parents=True, exist_ok=True)
    _workspace = path


# Ensure Python child processes output UTF-8 on Windows, where system locale
# defaults to cp936/GBK. We pass this env dict explicitly to every subprocess
# call so that PYTHONIOENCODING is set regardless of the parent's environment.
_PY_ENV = _os.environ.copy()
_PY_ENV["PYTHONIOENCODING"] = "utf-8"
_PY_ENV["PYTHONUTF8"] = "1"
_PY_ENV.pop("PYTHONLEGACYWINDOWSSTDIO", None)


def _run(*args, **kwargs):
    """subprocess.run wrapper that injects UTF-8 env vars and workspace cwd."""
    kwargs.setdefault("env", _PY_ENV)
    kwargs.setdefault("cwd", _workspace)
    return subprocess.run(*args, **kwargs)


def _popen(*args, **kwargs):
    """subprocess.Popen wrapper that injects UTF-8 env vars and workspace cwd."""
    kwargs.setdefault("env", _PY_ENV)
    kwargs.setdefault("cwd", _workspace)
    return subprocess.Popen(*args, **kwargs)


SUPPORTED_LANGUAGES = {"python", "javascript", "typescript", "bash", "shell", "c", "cpp", "cmd", "powershell", "bat", "ps1"}

# Template configs — the actual command paths may be overridden per-language
# via the environment config stored in the Language model.
_BASE_LANG_CONFIG = {
    "python":     {"ext": ".py",  "cmd": [_PYTHON, "-u"]},
    "javascript": {"ext": ".js",  "cmd": ["node"]},
    "typescript": {"ext": ".ts",  "cmd": ["tsx"],              "shell": True, "typecheck_cmd": ["tsc", "--noEmit"]},
    "bash":       {"ext": ".sh",  "cmd": ["bash"],       "shell": True},
    "shell":      {"ext": ".sh",  "cmd": ["bash"],       "shell": True},
    "c":          {"ext": ".c",   "compile_cmd": ["gcc"],   "run_ext": _EXE_SUFFIX, "timeout": CODE_C_RUN_TIMEOUT},
    "cpp":        {"ext": ".cpp", "compile_cmd": ["g++", "-std=c++17"], "run_ext": _EXE_SUFFIX, "timeout": CODE_C_RUN_TIMEOUT},
    "cmd":        {"ext": ".bat", "cmd": ["cmd", "/c"],         "shell": True},
    "powershell": {"ext": ".ps1", "cmd": ["powershell", "-File"], "shell": True},
    "bat":        {"ext": ".bat", "cmd": ["cmd", "/c"],         "shell": True},
    "ps1":        {"ext": ".ps1", "cmd": ["powershell", "-File"], "shell": True},
}

# Cache of merged config overrides per language — cleared when env config changes
_env_overrides: dict[str, dict] = {}

def _collect_env_overrides() -> tuple[dict, list[str]]:
    """Read all languages' env_config from DB and collect PATH entries.

    Returns ``(all_configs, path_entries)`` where ``all_configs`` is a dict
    mapping language name → config fields, and ``path_entries`` is the
    deduplicated list of directories to prepend to PATH.
    """
    all_configs: dict[str, dict] = {}
    path_entries: list[str] = []

    try:
        from database import SessionLocal
        from models import Language
        db = SessionLocal()
        try:
            for row in db.query(Language).all():
                if not row.env_config:
                    continue
                ec = row.env_config
                rp = ec.get("runtime_path")
                tsx = ec.get("tsx_path")
                tsc = ec.get("tsc_path")

                all_configs[row.name] = {
                    "runtime_path": rp,
                    "tsx_path": tsx,
                    "tsc_path": tsc,
                    "compile_flags": ec.get("compile_flags"),
                }

                # Collect PATH entries from ALL languages
                if rp:
                    parent = str(Path(rp).parent)
                    if parent not in path_entries:
                        path_entries.append(parent)
                    if _IS_WIN:
                        scripts = str(Path(rp).parent / "Scripts")
                        if Path(scripts).exists() and scripts not in path_entries:
                            path_entries.append(scripts)
                if tsx:
                    tsx_dir = str(Path(tsx).parent)
                    if tsx_dir not in path_entries:
                        path_entries.append(tsx_dir)
                if tsc:
                    tsc_dir = str(Path(tsc).parent)
                    if tsc_dir not in path_entries:
                        path_entries.append(tsc_dir)
        finally:
            db.close()
    except Exception:
        _log.warning("Failed to load env configs from DB, using defaults")

    return all_configs, path_entries


def _resolve_lang_config(lang: str) -> dict:
    """Return the resolved config for `lang`, with any user-saved env_config applied.

    The returned dict includes an ``env`` key: a copy of ``_PY_ENV`` with the
    directories of ALL languages' custom runtime/compiler paths prepended to
    PATH.  This ensures that e.g. a bash code block can find the user's
    custom python / pip / gcc.
    """
    if lang in _env_overrides:
        return _env_overrides[lang]

    base = _BASE_LANG_CONFIG[lang].copy()

    # On Windows, always use cmd for bash/shell — bash/WSL is unreliable
    if lang in ("bash", "shell") and _IS_WIN:
        base.update({"cmd": ["cmd", "/c"], "ext": ".bat", "inline": True})

    env = _PY_ENV.copy()

    all_configs, path_entries = _collect_env_overrides()

    # Apply command overrides for the current language
    cur = all_configs.get(lang, {})
    rp = cur.get("runtime_path")
    tsx = cur.get("tsx_path")
    tsc = cur.get("tsc_path")
    compile_flags = cur.get("compile_flags")

    if rp:
        if "cmd" in base:
            base["cmd"] = [rp] + base["cmd"][1:]
        if "compile_cmd" in base:
            base["compile_cmd"] = [rp] + base["compile_cmd"][1:]
    if tsx and "cmd" in base:
        base["cmd"] = [tsx] + base["cmd"][1:]
    if tsc and "typecheck_cmd" in base:
        base["typecheck_cmd"] = [tsc] + base["typecheck_cmd"][1:]
    if compile_flags and "compile_cmd" in base:
        base["compile_cmd"] = base["compile_cmd"][:1] + compile_flags.split() + base["compile_cmd"][1:]

    # Prepend ALL custom paths to PATH so subprocess calls find them first
    if path_entries:
        sep = ";" if _IS_WIN else ":"
        current_path = env.get("PATH", "")
        env["PATH"] = sep.join(path_entries) + sep + current_path

    base["env"] = env
    _env_overrides[lang] = base
    return base


def invalidate_env_config_cache(lang: str) -> None:
    """Clear all cached configs after user updates env settings.

    PATH entries are shared across languages, so updating one language's config
    requires recomputing the env for all."""
    _env_overrides.clear()

class CodeRunRequest(BaseModel):
    code: str
    language: str = "python"


@router.post("/code/run")
def run_code(body: CodeRunRequest):
    lang = body.language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unsupported language: {body.language}. Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}",
        )

    if len(body.code) > CODE_MAX_LENGTH:
        return {"stdout": "", "stderr": f"Code too long ({len(body.code)} chars, max {CODE_MAX_LENGTH})", "exit_code": 1, "duration_ms": 0}

    config = _resolve_lang_config(lang)
    _run_env = config.get("env", _PY_ENV)

    start = time.perf_counter()
    tmp_path: str | None = None

    try:
        if config.get("inline"):
            proc = _run(
                [*config["cmd"], body.code],
                capture_output=True,
                encoding="utf-8", errors="replace",
                timeout=CODE_TIMEOUT, env=_run_env,
            )
        else:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=config["ext"], delete=False, encoding="utf-8",
                dir=_workspace,
            ) as f:
                f.write(body.code)
                tmp_path = f.name

            # TypeScript type-check before execution
            typecheck_cmd = config.get("typecheck_cmd")
            if typecheck_cmd:
                tc = _run(
                    f'{typecheck_cmd[0]} {typecheck_cmd[1]} "{tmp_path}"',
                    capture_output=True, encoding="utf-8", errors="replace", timeout=CODE_TIMEOUT, shell=True, env=_run_env,
                )
                if tc.returncode != 0:
                    duration_ms = round((time.perf_counter() - start) * 1000)
                    return {
                        "stdout": "",
                        "stderr": tc.stdout,
                        "exit_code": tc.returncode,
                        "duration_ms": duration_ms,
                    }

            # C/C++ compile+run: compile first, then execute the binary
            if config.get("compile_cmd"):
                import os as _os
                exe_path = tmp_path.replace(config["ext"], config.get("run_ext", ""))
                compile_proc = _run(
                    [*config["compile_cmd"], tmp_path, "-o", exe_path],
                    capture_output=True, encoding="utf-8", errors="replace",
                    timeout=CODE_COMPILE_TIMEOUT, env=_run_env,
                )
                if compile_proc.returncode != 0:
                    duration_ms = round((time.perf_counter() - start) * 1000)
                    return {
                        "stdout": "",
                        "stderr": compile_proc.stderr or compile_proc.stdout,
                        "exit_code": compile_proc.returncode,
                        "duration_ms": duration_ms,
                    }
                proc = _run(
                    [exe_path],
                    capture_output=True, encoding="utf-8", errors="replace",
                    timeout=config.get("timeout", CODE_TIMEOUT),
                )
                try:
                    _os.unlink(exe_path)
                except Exception:
                    pass
                duration_ms = round((time.perf_counter() - start) * 1000)
                return {
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "exit_code": proc.returncode,
                    "duration_ms": duration_ms,
                }

            if config.get("shell"):
                proc = _run(
                    f'{" ".join(config["cmd"])} "{tmp_path}"',
                    capture_output=True, encoding="utf-8", errors="replace", timeout=CODE_TIMEOUT, shell=True, env=_run_env,
                )
            else:
                proc = _run(
                    [*config["cmd"], tmp_path],
                    capture_output=True, encoding="utf-8", errors="replace", timeout=CODE_TIMEOUT, env=_run_env,
                )

        duration_ms = round((time.perf_counter() - start) * 1000)
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.perf_counter() - start) * 1000)
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {CODE_TIMEOUT}s",
            "exit_code": 124,
            "duration_ms": duration_ms,
        }
    except FileNotFoundError:
        duration_ms = round((time.perf_counter() - start) * 1000)
        return {
            "stdout": "",
            "stderr": f"{config['cmd'][0]} not found. Is it installed?",
            "exit_code": 127,
            "duration_ms": duration_ms,
        }
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/code/run/stream")
def run_code_stream(body: CodeRunRequest):
    lang = body.language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unsupported language: {body.language}. Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}",
        )

    if len(body.code) > CODE_MAX_LENGTH:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Code too long")

    config = _resolve_lang_config(lang)
    _run_env = config.get("env", _PY_ENV)

    def generate():
        start = time.perf_counter()
        tmp_path: str | None = None
        proc = None

        try:
            if config.get("inline"):
                proc = _popen(
                    [*config["cmd"], body.code],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    encoding="utf-8", errors="replace", bufsize=1, env=_run_env,
                )
            else:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=config["ext"], delete=False, encoding="utf-8",
                    dir=_workspace,
                ) as f:
                    f.write(body.code)
                    tmp_path = f.name

                # TypeScript type-check before execution
                typecheck_cmd = config.get("typecheck_cmd")
                if typecheck_cmd:
                    tc = _run(
                        f'{typecheck_cmd[0]} {typecheck_cmd[1]} "{tmp_path}"',
                        capture_output=True, encoding="utf-8", errors="replace", timeout=CODE_TIMEOUT, shell=True, env=_run_env,
                    )
                    if tc.returncode != 0:
                        duration_ms = round((time.perf_counter() - start) * 1000)
                        yield f"event: stderr\ndata: {json.dumps({'text': tc.stdout})}\n\n"
                        yield f"event: done\ndata: {json.dumps({'exit_code': tc.returncode, 'duration_ms': duration_ms})}\n\n"
                        return

                # C/C++ compile+run: compile first, then execute the binary
                if config.get("compile_cmd"):
                    import os as _os
                    exe_path = tmp_path.replace(config["ext"], config.get("run_ext", ""))
                    compile_proc = _run(
                        [*config["compile_cmd"], tmp_path, "-o", exe_path],
                        capture_output=True, encoding="utf-8", errors="replace",
                        timeout=CODE_COMPILE_TIMEOUT, env=_run_env,
                    )
                    if compile_proc.returncode != 0:
                        duration_ms = round((time.perf_counter() - start) * 1000)
                        err_text = compile_proc.stderr or compile_proc.stdout
                        yield f"event: stderr\ndata: {json.dumps({'text': err_text})}\n\n"
                        yield f"event: done\ndata: {json.dumps({'exit_code': compile_proc.returncode, 'duration_ms': duration_ms})}\n\n"
                        return

                    proc = _popen(
                        [exe_path],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        encoding="utf-8", errors="replace", bufsize=1,
                    )

                    q: queue.Queue[tuple[str, str]] = queue.Queue()
                    stdout_done = threading.Event()
                    stderr_done = threading.Event()

                    def read_stream(stream, event_name):
                        try:
                            for line in iter(stream.readline, ""):
                                if line:
                                    q.put((event_name, line))
                        except Exception:
                            q.put(("stderr", f"{event_name} read error"))
                        finally:
                            if event_name == "stdout":
                                stdout_done.set()
                            else:
                                stderr_done.set()

                    t1 = threading.Thread(target=read_stream, args=(proc.stdout, "stdout"), daemon=True)
                    t2 = threading.Thread(target=read_stream, args=(proc.stderr, "stderr"), daemon=True)
                    t1.start()
                    t2.start()

                    while not (stdout_done.is_set() and stderr_done.is_set()):
                        try:
                            event, text = q.get(timeout=CODE_QUEUE_POLL)
                            yield f"event: {event}\ndata: {json.dumps({'text': text})}\n\n"
                        except queue.Empty:
                            pass

                    while True:
                        try:
                            event, text = q.get_nowait()
                            yield f"event: {event}\ndata: {json.dumps({'text': text})}\n\n"
                        except queue.Empty:
                            break

                    t1.join()
                    t2.join()
                    proc.wait(timeout=config.get("timeout", 10))
                    try:
                        _os.unlink(exe_path)
                    except Exception:
                        pass
                    duration_ms = round((time.perf_counter() - start) * 1000)
                    yield f"event: done\ndata: {json.dumps({'exit_code': proc.returncode, 'duration_ms': duration_ms})}\n\n"
                    return

                if config.get("shell"):
                    proc = _popen(
                        f'{" ".join(config["cmd"])} "{tmp_path}"',
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        encoding="utf-8", errors="replace", bufsize=1, shell=True, env=_run_env,
                    )
                else:
                    proc = _popen(
                        [*config["cmd"], tmp_path],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        encoding="utf-8", errors="replace", bufsize=1, env=_run_env,
                    )

            q: queue.Queue[tuple[str, str]] = queue.Queue()
            stdout_done = threading.Event()
            stderr_done = threading.Event()

            def read_stream(stream, event_name):
                try:
                    for line in iter(stream.readline, ""):
                        if line:
                            q.put((event_name, line))
                except Exception:
                    q.put(("stderr", f"{event_name} read error"))
                finally:
                    if event_name == "stdout":
                        stdout_done.set()
                    else:
                        stderr_done.set()

            t1 = threading.Thread(target=read_stream, args=(proc.stdout, "stdout"), daemon=True)
            t2 = threading.Thread(target=read_stream, args=(proc.stderr, "stderr"), daemon=True)
            t1.start()
            t2.start()

            # Drain queue until both streams are done
            while not (stdout_done.is_set() and stderr_done.is_set()):
                try:
                    event, text = q.get(timeout=CODE_QUEUE_POLL)
                    yield f"event: {event}\ndata: {json.dumps({'text': text})}\n\n"
                except queue.Empty:
                    pass

            # Drain remaining items
            while True:
                try:
                    event, text = q.get_nowait()
                    yield f"event: {event}\ndata: {json.dumps({'text': text})}\n\n"
                except queue.Empty:
                    break

            t1.join()
            t2.join()
            proc.wait(timeout=CODE_TIMEOUT)
            duration_ms = round((time.perf_counter() - start) * 1000)
            yield f"event: done\ndata: {json.dumps({'exit_code': proc.returncode, 'duration_ms': duration_ms})}\n\n"

        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
            duration_ms = round((time.perf_counter() - start) * 1000)
            timeout_msg = f"Execution timed out after {CODE_TIMEOUT}s\n"
            yield f"event: stderr\ndata: {json.dumps({'text': timeout_msg})}\n\n"
            yield f"event: done\ndata: {json.dumps({'exit_code': 124, 'duration_ms': duration_ms})}\n\n"
        except FileNotFoundError:
            duration_ms = round((time.perf_counter() - start) * 1000)
            not_found_msg = f"{config['cmd'][0]} not found\n"
            yield f"event: stderr\ndata: {json.dumps({'text': not_found_msg})}\n\n"
            yield f"event: done\ndata: {json.dumps({'exit_code': 127, 'duration_ms': duration_ms})}\n\n"
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    pass

    return StreamingResponse(generate(), media_type="text/event-stream")
