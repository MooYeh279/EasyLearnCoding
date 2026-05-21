#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()  { echo -e "        ${GREEN}[OK]${NC}"; }
fail(){ echo -e "        ${RED}[FAIL]${NC} $1"; exit 1; }

echo ""
echo -e "  ${BOLD}+-----------------------------------+${NC}"
echo -e "  ${BOLD}|     Learn Coding  -  Setup        |${NC}"
echo -e "  ${BOLD}+-----------------------------------+${NC}"
echo ""

# ---- Step 1: Python --------------------------------------------------
echo "  [1/4] Python runtime"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        if [ -n "$ver" ]; then
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -gt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -ge 10 ]); then
                PYTHON="$cmd"
                break
            fi
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    fail "Python >= 3.10 required  (https://python.org)"
fi
echo -e "        $($PYTHON --version)"
ok

# ---- Step 2: Node.js -------------------------------------------------
echo ""
echo "  [2/4] Node.js runtime"
if ! command -v node &>/dev/null; then
    fail "Node.js not found  (https://nodejs.org)"
fi
node_ver=$(node --version | grep -oP '\d+' | head -1)
if [ "$node_ver" -lt 18 ] 2>/dev/null; then
    fail "Node.js >= 18 required, got: $(node --version)"
fi
echo -e "        $(node --version)"
ok

# ---- Step 3: Python package ------------------------------------------
echo ""
echo "  [3/4] Python package (pip install)"
echo ""
$PYTHON -m pip install --user -e "$BACKEND_DIR" || fail "pip install failed"
echo ""
ok

# ---- Step 4: Frontend build + DB seed --------------------------------
echo ""
echo "  [4/4] Frontend build & database"
echo ""
cd "$FRONTEND_DIR"
npm install || fail "npm install failed"
npm run build || fail "npm build failed"

cd "$SCRIPT_DIR"
$PYTHON "$BACKEND_DIR/seed.py" || fail "database seed failed"
echo ""
ok

# ---- Done ------------------------------------------------------------
USER_BIN=$($PYTHON -c "import site,os; print(os.path.join(site.USER_BASE,'bin'))" 2>/dev/null || echo "")

echo ""
echo -e "  ${BOLD}+-----------------------------------+${NC}"
echo -e "  ${BOLD}|  All done.                        |${NC}"
echo -e "  ${BOLD}|                                   |${NC}"
echo -e "  ${BOLD}|  Start  : learn-code              |${NC}"
echo -e "  ${BOLD}|  URL    : http://localhost:8000   |${NC}"
echo -e "  ${BOLD}+-----------------------------------+${NC}"
echo ""

if [ -n "$USER_BIN" ] && ! echo "$PATH" | tr ':' '\n' | grep -qF "$USER_BIN"; then
    echo -e "  ${CYAN}Note:${NC} $USER_BIN is not on PATH."
    echo -e "  Add this to ~/.bashrc or ~/.zshrc:"
    echo ""
    echo -e "    ${CYAN}export PATH=\"\$PATH:$USER_BIN\"${NC}"
    echo ""
fi
