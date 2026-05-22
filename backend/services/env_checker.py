import subprocess
import re
import platform
from dataclasses import dataclass, field
from typing import Optional

from config import ENV_CHECK_TIMEOUT, ENV_CHECK_CACHE_TTL

# Each language maps to a list of [command, component_name] pairs.
# The component name is used for install guide lookup.
COMMANDS: dict[str, list[tuple[list[str], str]]] = {
    "python":     [(["python", "--version"], "python"),  (["pip", "--version"], "pip")],
    "javascript": [(["node", "--version"], "node"),      (["npm", "--version"], "npm")],
    "typescript": [(["node", "--version"], "node"),      (["tsx", "--version"], "tsx"), (["tsc", "--version"], "tsc")],
    "bash":       [(["bash", "--version"], "bash")],
    "c":          [(["gcc", "--version"], "gcc")],
    "cpp":        [(["g++", "--version"], "gpp")],
}

VERSION_PATTERNS: dict[str, str] = {
    "python": r"Python (\d+\.\d+\.\d+)",
    "node":   r"v(\d+\.\d+\.\d+)",
    "tsx":    r"v?(\d+\.\d+\.\d+)",
    "tsc":    r"[Vv]ersion\s+(\d+\.\d+\.\d+)",
    "pip":    r"(\d+\.\d+\.\d+)",
    "npm":    r"(\d+\.\d+\.\d+)",
    "bash":   r"(\d+\.\d+\.\d+)",
    "gcc":    r"(\d+\.\d+\.\d+)",
    "gpp":    r"(\d+\.\d+\.\d+)",
}

# OS-adaptive install commands
def _get_os() -> str:
    s = platform.system()
    if s == "Windows":
        return "win"
    elif s == "Darwin":
        return "mac"
    return "linux"

INSTALL_GUIDE: dict[str, dict[str, str]] = {
    "python": {
        "win":   "winget install Python.Python.3.12",
        "mac":   "brew install python@3.12",
        "linux": "sudo apt-get install -y python3",
    },
    "pip": {
        "win":   "python -m ensurepip --upgrade",
        "mac":   "python3 -m ensurepip --upgrade",
        "linux": "sudo apt-get install -y python3-pip",
    },
    "node": {
        "win":   "winget install OpenJS.NodeJS.LTS",
        "mac":   "brew install node",
        "linux": "sudo apt-get install -y nodejs",
    },
    "npm": {
        "any": "npm install -g npm@latest",
    },
    "tsx": {
        "any": "npm install -g tsx",
    },
    "tsc": {
        "any": "npm install -g typescript",
    },
    "bash": {
        "win":   "echo Install Git Bash from https://git-scm.com",
        "mac":   "brew install bash",
        "linux": "sudo apt-get install -y bash",
    },
    "gcc": {
        "win":   'winget install --id=MartinStorsjo.LLVM-MinGW.MSVCRT -e',
        "mac":   "brew install gcc",
        "linux": "sudo apt-get install -y build-essential",
    },
    "gpp": {
        "win":   'winget install --id=MartinStorsjo.LLVM-MinGW.MSVCRT -e',
        "mac":   "brew install gcc",
        "linux": "sudo apt-get install -y g++",
    },
}

def _get_install_cmd(component: str) -> str | None:
    """Return OS-appropriate install command for a component, or None."""
    guide = INSTALL_GUIDE.get(component)
    if not guide:
        return None
    os_name = _get_os()
    return guide.get(os_name) or guide.get("any")


@dataclass
class LanguageEnvironment:
    language: str
    runtime_available: bool
    runtime_path: Optional[str] = None
    version: Optional[str] = None
    package_manager: Optional[str] = None
    package_manager_ok: bool = False
    config_override: Optional[dict] = field(default_factory=dict)
    components: list[dict] = field(default_factory=list)
    ready: bool = False
    os: str = ""


# Simple in-memory cache
_cache: dict[str, tuple[float, LanguageEnvironment]] = {}


def invalidate_check_cache(language: str | None = None) -> None:
    """Clear cached env check results. If language is None, clear all."""
    if language is None:
        _cache.clear()
    else:
        _cache.pop(language, None)


def check_environment(language: str, force: bool = False) -> LanguageEnvironment:
    if language not in COMMANDS:
        raise ValueError(f"Unsupported language: {language}")

    import time
    if not force and language in _cache:
        ts, result = _cache[language]
        if time.time() - ts < ENV_CHECK_CACHE_TTL:
            return result

    checks = COMMANDS[language]
    components: list[dict] = []
    all_ready = True
    primary_available = False
    primary_version = None
    primary_path = None
    pkg_mgr = None
    pkg_mgr_ok = False

    for cmd, comp_name in checks:
        available = False
        version = None
        path = cmd[0]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=ENV_CHECK_TIMEOUT,
                shell=(platform.system() == "Windows"),
            )
            output = result.stdout or ""
            # Reject if stderr contains error indicators
            stderr_lower = (result.stderr or "").lower()
            is_stderr_error = any(kw in stderr_lower for kw in (
                "not found", "no such file", "not recognized",
                "cannot find", "error", "cannot execute",
            ))
            if result.returncode == 0 and not is_stderr_error:
                pattern = VERSION_PATTERNS.get(comp_name, r"(\d+\.\d+\.\d+)")
                m = re.search(pattern, output)
                if m:
                    available = True
                    version = m.group(1)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            pass

        install_cmd = _get_install_cmd(comp_name)

        components.append({
            "name": comp_name,
            "available": available,
            "version": version,
            "path": path,
            "install_cmd": install_cmd,
        })

        if not available:
            all_ready = False

        # Track primary runtime (first command is always the main runtime)
        if comp_name == COMMANDS[language][0][1]:
            primary_available = available
            primary_version = version
            primary_path = path

        # Track package manager (second command if exists)
        if len(COMMANDS[language]) > 1 and comp_name == COMMANDS[language][1][1]:
            pkg_mgr = cmd[0]
            pkg_mgr_ok = available

    env = LanguageEnvironment(
        language=language,
        runtime_available=primary_available,
        runtime_path=primary_path,
        version=primary_version,
        package_manager=pkg_mgr,
        package_manager_ok=pkg_mgr_ok,
        components=components,
        ready=all_ready,
        os=_get_os(),
    )
    _cache[language] = (time.time(), env)
    return env
