from http import HTTPStatus
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import Language
from services.env_checker import check_environment

router = APIRouter(prefix="/api", tags=["environment"])


class EnvConfigUpdate(BaseModel):
    runtime_path: str | None = None
    compile_flags: str | None = None
    tsx_path: str | None = None
    tsc_path: str | None = None


def _detect_custom_path(path: str, *extra_args: str) -> tuple[bool, str | None]:
    """Try running `path extra_args` to detect version. Returns (available, version)."""
    import subprocess, re, platform
    try:
        cmd = [path] + list(extra_args) if extra_args else [path, "--version"]
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=10,
            shell=(platform.system() == "Windows"),
        )
        output = result.stdout or ""
        if result.returncode == 0:
            m = re.search(r"(\d+\.\d+\.\d+)", output)
            if m:
                return True, m.group(1)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    return False, None


def _path_dir(p: str) -> str:
    """Extract the directory containing a binary path."""
    from pathlib import Path
    return str(Path(p).parent)


def _patch_components_with_config(env, config: dict):
    """Update components to reflect user-saved custom paths.

    General rules:
    - ``runtime_path`` is the primary runtime/compiler for the language.
      For python it also drives pip detection (via ``python -m pip``).
      For node it also drives npm detection (via ``<node_dir>/npm``).
    - ``tsx_path`` / ``tsc_path`` override TypeScript tool detection.
    """
    rp = config.get("runtime_path")
    rp_dir = _path_dir(rp) if rp else None
    tsx = config.get("tsx_path")
    tsc = config.get("tsc_path")

    for comp in env.components:
        name = comp["name"]
        custom_path = None
        custom_args: tuple[str, ...] = ()

        # Primary runtime / compiler
        if name in ("python", "node", "bash", "gcc", "gpp"):
            custom_path = rp
        # pip: belongs to the configured python
        elif name == "pip" and rp:
            custom_path = rp
            custom_args = ("-m", "pip", "--version")
        # npm: try <node_dir>/npm, also <node_dir>/Scripts/npm on Windows
        elif name == "npm" and rp_dir:
            import platform, os
            npm_name = "npm.cmd" if platform.system() == "Windows" else "npm"
            candidates = [os.path.join(rp_dir, npm_name)]
            if platform.system() == "Windows":
                candidates.append(os.path.join(rp_dir, "Scripts", npm_name))
            for candidate in candidates:
                if os.path.exists(candidate):
                    custom_path = candidate
                    break
        # Standalone overrides for TypeScript tools
        elif name == "tsx":
            custom_path = tsx
        elif name == "tsc":
            custom_path = tsc

        if custom_path:
            comp["path"] = custom_path
            ok, ver = _detect_custom_path(custom_path, *custom_args)
            comp["available"] = ok
            comp["version"] = ver

    # Recompute overall ready state
    env.ready = all(c["available"] for c in env.components)


@router.get("/environment/{language_name}")
def get_environment(language_name: str, force: bool = False, db: Session = Depends(get_db)):
    lang = db.query(Language).filter(Language.name == language_name).first()
    if not lang:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Language not found")

    env = check_environment(language_name, force=force)
    config = lang.env_config or {}
    env.config_override = config

    if config:
        _patch_components_with_config(env, config)

    return env


@router.put("/environment/{language_name}")
def update_environment_config(language_name: str, body: EnvConfigUpdate, db: Session = Depends(get_db)):
    lang = db.query(Language).filter(Language.name == language_name).first()
    if not lang:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Language not found")

    # Must create a NEW dict to trigger SQLAlchemy change detection on JSON column
    current = dict(lang.env_config or {})

    def _apply(key: str, value: str | None):
        if value is None:
            return  # not provided, keep existing
        if value == "":
            current.pop(key, None)  # empty = clear, use default
        else:
            current[key] = value

    _apply("runtime_path", body.runtime_path)
    _apply("compile_flags", body.compile_flags)
    _apply("tsx_path", body.tsx_path)
    _apply("tsc_path", body.tsc_path)

    lang.env_config = current
    db.commit()

    from routers.code_executor import invalidate_env_config_cache
    from services.env_checker import invalidate_check_cache
    invalidate_env_config_cache(language_name)
    invalidate_check_cache(language_name)

    return {"message": "Config updated", "env_config": current}
