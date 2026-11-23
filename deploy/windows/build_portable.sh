#!/usr/bin/env bash
# Builds the Windows (x64) package of OFFLINE SHARE on macOS/Linux - no Windows machine needed.
#   * bundles the official Windows "embeddable" Python 3.12 from python.org
#   * installs Windows (win_amd64) wheels of every dependency into it
#   * adds the backend, the built frontend, scripts and docs
# Output:  build/OfflineShare/                          (the installed layout)
#          build/installer/OFFLINE_SHARE_Windows_x64.zip (portable package)
#          build/installer/OFFLINE_SHARE_Server_Setup.exe (NSIS installer, if makensis is available)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
B="$ROOT/build"
PYVER=3.12.10
PYZIP="$B/downloads/python-$PYVER-embed-amd64.zip"
PY="$ROOT/backend/.venv/bin/python"
OUT="$B/OfflineShare"
APPVER=$(grep -E '^APP_VERSION' "$ROOT/backend/app/config.py" | cut -d'"' -f2)

echo "==> OFFLINE SHARE $APPVER  (Windows x64, Python $PYVER)"
mkdir -p "$B/downloads" "$B/installer"
[ -f "$PYZIP" ] || curl -sSfL -o "$PYZIP" "https://www.python.org/ftp/python/$PYVER/python-$PYVER-embed-amd64.zip"

echo "==> frontend build"
(cd "$ROOT/frontend" && npx tsc -b && npx vite build >/dev/null)

echo "==> Windows wheels"
grep -v pywin32 "$ROOT/backend/requirements.txt" | grep -v '^#' | grep . > "$B/requirements-win.txt"
printf 'colorama\ntzdata\n' >> "$B/requirements-win.txt"
rm -rf "$B/wheels"
"$PY" -m pip download --quiet -r "$B/requirements-win.txt" -d "$B/wheels" \
  --platform win_amd64 --python-version 3.12 --implementation cp --only-binary=:all:

echo "==> assemble $OUT"
rm -rf "$OUT"; mkdir -p "$OUT/python/Lib/site-packages" "$OUT/backend" "$OUT/frontend" "$OUT/docs"
unzip -q "$PYZIP" -d "$OUT/python"
for w in "$B"/wheels/*.whl; do unzip -q -o "$w" -d "$OUT/python/Lib/site-packages"; done
# drop wheel .data/script folders that are not needed at runtime
find "$OUT/python/Lib/site-packages" -maxdepth 1 -name "*.data" -type d -exec rm -rf {} +
# let the embedded interpreter see site-packages and the backend
cat > "$OUT/python/python312._pth" <<'PTH'
python312.zip
.
Lib\site-packages
..\backend
import site
PTH
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$ROOT/backend/app" "$OUT/backend/"
cp "$ROOT/backend/offline_share.py" "$ROOT/backend/requirements.txt" "$OUT/backend/"
rsync -a "$ROOT/frontend/dist" "$OUT/frontend/"
cp "$ROOT"/docs/*.md "$ROOT"/docs/*.pdf "$ROOT/docs/database_schema.sql" "$OUT/docs/" 2>/dev/null || true
cp "$ROOT/deploy/windows/portable/"* "$OUT/"
cp "$ROOT/README.md" "$OUT/README.md"
cat > "$OUT/VERSION.txt" <<VER
OFFLINE SHARE $APPVER  -  Windows x64 package
Built $(date '+%d/%m/%Y %H:%M')  -  bundled Python $PYVER (python.org embeddable)
VER
# Windows line endings for every script (LF-only .bat files can break labels in cmd.exe)
for f in "$OUT"/*.bat "$OUT"/*.cmd "$OUT"/*.ps1 "$OUT"/*.txt; do
  perl -pi -e 's/\r?\n/\r\n/' "$f"
done

echo "==> sanity checks"
grep -q "ENABLE_FTS5" <(strings "$OUT/python/sqlite3.dll") && echo "   sqlite FTS5: yes"
test -f "$OUT/frontend/dist/index.html" && echo "   frontend: yes"
ls "$OUT/python/Lib/site-packages" | grep -qi pydantic_core && echo "   pydantic_core (win_amd64): yes"
file "$OUT/python/Lib/site-packages/pydantic_core/"*.pyd | grep -q "x86-64" && echo "   native modules are Windows x64: yes"

echo "==> zip"
rm -f "$B/installer/OFFLINE_SHARE_Windows_x64.zip"
(cd "$B" && zip -qr -9 "installer/OFFLINE_SHARE_Windows_x64.zip" OfflineShare)

if command -v makensis >/dev/null; then
  echo "==> NSIS installer"
  makensis -V2 -DAPPVER="$APPVER" -DSRC="$OUT" -DOUTFILE="$B/installer/OFFLINE_SHARE_Server_Setup.exe" \
    "$ROOT/deploy/windows/OFFLINE_SHARE_Server_Setup.nsi"
fi
ls -lh "$B/installer"
