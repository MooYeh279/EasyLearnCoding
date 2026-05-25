"""Unified code execution service.

Provides a single `execute_code()` function that handles writing temp files,
compiling (C/C++), and running code in any supported language.
Both the course lesson runner (code_executor) and the exercise runner
(exercise_service) delegate here for the actual subprocess execution.
"""
from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from logger import get_logger

logger = get_logger("code_runner")

_IS_WIN = platform.system() == "Windows"
_EXE_SUFFIX = ".exe" if _IS_WIN else ""


@dataclass
class ExecutionResult:
    """Structured result from a code execution."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: int = 0
    error: str | None = None  # "Compilation failed: ..." / "Execution timed out"


def execute_code(
    language: str,
    code: str,
    *,
    timeout: int = 15,
    suppress_warnings: bool = False,
    cwd: str | None = None,
    compile_timeout: int | None = None,
    native: bool = False,
) -> ExecutionResult:
    """Execute *code* in the given *language* and return the result.

    Resolves the language config (command paths, env vars) from the canonical
    ``code_executor._resolve_lang_config``.  Writes a temp file, compiles if
    needed (C/C++), runs, and captures stdout/stderr.

    Parameters
    ----------
    language:
        One of python, javascript, typescript, c, cpp, bash, shell.
    code:
        The source code to execute.
    timeout:
        Max seconds for the *run* step (default 15).
    suppress_warnings:
        If True, pass ``-w`` to the C/C++ compiler to suppress warnings.
    cwd:
        Working directory for the subprocess.  Defaults to the configured
        workspace (from code_executor) or a temp directory.
    compile_timeout:
        Max seconds for the compile step (C/C++).  Defaults to *timeout*.
    native:
        If True, skip platform compatibility overrides (e.g. bash→cmd on
        Windows) so the code runs in the actual target language.
        Exercise validation uses native=True because test harness scripts
        are written in the target language syntax.
    """
    from routers.code_executor import _resolve_lang_config, _PY_ENV, _workspace

    config = _resolve_lang_config(language, native=native)
    env = config.get("env", _PY_ENV.copy())
    work_dir = cwd or _workspace

    if compile_timeout is None:
        compile_timeout = timeout

    tmp_path: str | None = None
    bin_path: str | None = None

    try:
        # --- Inline execution (e.g. bash-on-windows) ---
        if config.get("inline"):
            result = _run_subprocess(
                [*config["cmd"], code],
                env=env, cwd=work_dir, timeout=timeout,
            )
            return _make_result(result, time.perf_counter())

        # --- Write temp file ---
        ext = config.get("ext", ".txt")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False, encoding="utf-8", dir=work_dir,
        ) as f:
            f.write(code)
            tmp_path = f.name

        # --- TypeScript type-check (skipped for exercise validation) ---
        # The exercise path never needs type-checking; only the course lesson
        # runner uses it.  We skip it here and let code_executor handle it
        # separately if needed.

        # --- C/C++ compile + run ---
        if config.get("compile_cmd"):
            compile_cmd = list(config["compile_cmd"])
            exe_path = tmp_path.replace(ext, config.get("run_ext", _EXE_SUFFIX))
            bin_path = exe_path

            extra_flags = []
            if suppress_warnings:
                extra_flags.append("-w")

            compile_result = _run_subprocess(
                [*compile_cmd, *extra_flags, tmp_path, "-o", exe_path],
                env=env, cwd=work_dir, timeout=compile_timeout,
            )
            if compile_result.returncode != 0:
                err = compile_result.stderr or compile_result.stdout
                return ExecutionResult(
                    stderr=err,
                    exit_code=compile_result.returncode,
                    error=f"Compilation failed: {err[-300:]}",
                )

            run_result = _run_subprocess(
                [exe_path],
                env=env, cwd=work_dir,
                timeout=config.get("timeout", timeout),
            )
            # Clean up binary immediately
            _safe_unlink(exe_path)
            bin_path = None
            return _make_result(run_result, time.perf_counter())

        # --- Shell execution (tsx, etc.) ---
        if config.get("shell"):
            cmd_str = f'{" ".join(config["cmd"])} "{tmp_path}"'
            result = _run_subprocess(
                cmd_str, env=env, cwd=work_dir, timeout=timeout, shell=True,
            )
            return _make_result(result, time.perf_counter())

        # --- Standard execution (python -u file, node file, bash file) ---
        result = _run_subprocess(
            [*config["cmd"], tmp_path],
            env=env, cwd=work_dir, timeout=timeout,
        )
        return _make_result(result, time.perf_counter())

    except subprocess.TimeoutExpired:
        return ExecutionResult(error=f"Execution timed out ({timeout}s)", exit_code=124)
    except FileNotFoundError as e:
        return ExecutionResult(error=f"Command not found: {e}", exit_code=127)
    except Exception as e:
        logger.exception("Code execution exception: %s", e)
        return ExecutionResult(error=str(e), exit_code=1)
    finally:
        _safe_unlink(tmp_path)
        _safe_unlink(bin_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_subprocess(
    args: list[str] | str,
    *,
    env: dict,
    cwd: str,
    timeout: int,
    shell: bool = False,
) -> subprocess.CompletedProcess:
    """subprocess.run wrapper with consistent encoding and error handling."""
    return subprocess.run(
        args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        cwd=cwd,
        shell=shell,
    )


def _make_result(
    proc: subprocess.CompletedProcess,
    start: float,
) -> ExecutionResult:
    """Convert a CompletedProcess into an ExecutionResult."""
    duration_ms = int((time.perf_counter() - start) * 1000)
    return ExecutionResult(
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        exit_code=proc.returncode,
        duration_ms=duration_ms,
    )


def _safe_unlink(path: str | None) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except Exception:
        pass
