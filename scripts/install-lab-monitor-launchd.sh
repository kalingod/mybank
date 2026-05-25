#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${LABEL:-com.mybank.lab-monitor}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18081}"
INTERVAL="${INTERVAL:-1}"
VIA="${VIA:-exp2}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
PLIST_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${HOME}/Library/Logs"
PLIST="${PLIST_DIR}/${LABEL}.plist"
GUI_DOMAIN="gui/$(id -u)"

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "python3 not found: ${PYTHON_BIN}" >&2
  exit 1
fi

mkdir -p "${PLIST_DIR}" "${LOG_DIR}"

cat > "${PLIST}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${ROOT}/scripts/lab-monitor-web.py</string>
    <string>--via</string>
    <string>${VIA}</string>
    <string>--host</string>
    <string>${HOST}</string>
    <string>--port</string>
    <string>${PORT}</string>
    <string>--interval</string>
    <string>${INTERVAL}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/mybank-lab-monitor.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/mybank-lab-monitor.err.log</string>
</dict>
</plist>
PLIST

plutil -lint "${PLIST}" >/dev/null

launchctl bootout "${GUI_DOMAIN}" "${PLIST}" >/dev/null 2>&1 || true
pkill -f "lab-monitor-web.py.*--port[[:space:]]+${PORT}" >/dev/null 2>&1 || true
launchctl bootstrap "${GUI_DOMAIN}" "${PLIST}"
launchctl enable "${GUI_DOMAIN}/${LABEL}"
launchctl kickstart -k "${GUI_DOMAIN}/${LABEL}"

sleep 2
curl --noproxy '*' -fsS "http://${HOST}:${PORT}/api/snapshot" >/dev/null

echo "installed ${LABEL}"
echo "url: http://${HOST}:${PORT}/"
echo "plist: ${PLIST}"
echo "logs: ${LOG_DIR}/mybank-lab-monitor.log ${LOG_DIR}/mybank-lab-monitor.err.log"
