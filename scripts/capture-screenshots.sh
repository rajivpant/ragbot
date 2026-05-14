#!/usr/bin/env bash
# capture-screenshots.sh — Prepare the Ragbot stack for v3.4 screenshot capture.
#
# This script starts the stack in demo mode, waits for /health to confirm
# demo_mode=true, then prints the URL list with the recommended viewport
# for each screenshot. It does NOT take any screenshot itself — that step
# is manual via the operator's browser.
#
# Usage:
#   ./scripts/capture-screenshots.sh           # start, wait, print URL list
#   ./scripts/capture-screenshots.sh --stop    # stop the demo stack
#   ./scripts/capture-screenshots.sh --status  # show current demo stack state
#
# Companion: docs/screenshots/CAPTURE.md (the full capture procedure).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_DIR="$(dirname "${SCRIPT_DIR}")"
HEALTH_URL="http://localhost:8080/health"
WEB_URL="http://localhost:3000"
WAIT_TIMEOUT_SECONDS=120
WAIT_INTERVAL_SECONDS=2

color_bold() { printf '\033[1m%s\033[0m\n' "$1"; }
color_dim()  { printf '\033[2m%s\033[0m\n' "$1"; }
color_ok()   { printf '\033[32m%s\033[0m\n' "$1"; }
color_warn() { printf '\033[33m%s\033[0m\n' "$1"; }

usage() {
  cat <<'EOF'
capture-screenshots.sh — Prepare the Ragbot stack for v3.4 screenshot capture.

Usage:
  ./scripts/capture-screenshots.sh           Start demo stack, wait, print URL list
  ./scripts/capture-screenshots.sh --stop    Stop the demo stack
  ./scripts/capture-screenshots.sh --status  Show current demo stack state
  ./scripts/capture-screenshots.sh --help    Show this message

The companion document at docs/screenshots/CAPTURE.md is the full
capture procedure. Set your browser viewport to 1440x900 for
documentation captures and 2880x1800 for hero captures.
EOF
}

ensure_compose_available() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker is not installed or not on PATH." >&2
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "Error: 'docker compose' is not available. Install Docker Compose v2." >&2
    exit 1
  fi
}

start_demo_stack() {
  cd "${REPO_DIR}"
  color_bold "Starting Ragbot in demo mode (RAGBOT_DEMO=1)..."
  RAGBOT_DEMO=1 docker compose up -d
  echo
  color_dim "Waiting for ${HEALTH_URL} to report demo_mode=true..."

  local elapsed=0
  while [ "${elapsed}" -lt "${WAIT_TIMEOUT_SECONDS}" ]; do
    if curl -fsS "${HEALTH_URL}" 2>/dev/null | grep -q '"demo_mode":\s*true'; then
      color_ok "Demo stack is up. /health reports demo_mode=true."
      return 0
    fi
    sleep "${WAIT_INTERVAL_SECONDS}"
    elapsed=$((elapsed + WAIT_INTERVAL_SECONDS))
    printf '.'
  done

  echo
  color_warn "Timed out waiting for demo_mode=true after ${WAIT_TIMEOUT_SECONDS}s."
  color_warn "Inspect with 'docker compose logs' and re-run."
  exit 1
}

stop_demo_stack() {
  cd "${REPO_DIR}"
  color_bold "Stopping the demo stack..."
  docker compose down
  color_ok "Demo stack stopped."
}

status_demo_stack() {
  cd "${REPO_DIR}"
  docker compose ps
  echo
  if curl -fsS "${HEALTH_URL}" 2>/dev/null | grep -q '"demo_mode":\s*true'; then
    color_ok "/health reports demo_mode=true."
  else
    color_warn "/health is not reporting demo_mode=true. Stack may not be running in demo mode."
  fi
}

print_capture_checklist() {
  cat <<EOF

$(color_bold "Screenshot capture URL list (set viewport to 1440x900 unless noted):")

  1. Agent panel with multi-workspace
       URL:      ${WEB_URL}/
       Filename: docs/screenshots/agent-panel.png
       State:    Multi-workspace agent run with sub-agent dispatch + citations
                 (see CAPTURE.md screenshot #1 for the exact demo state)

  2. MCP settings panel
       URL:      ${WEB_URL}/  (Settings -> MCP servers tab)
       Filename: docs/screenshots/mcp-settings.png
       State:    Two server entries, one expanded showing the tool list

  3. Skills panel
       URL:      ${WEB_URL}/  (Settings -> Skills tab)
       Filename: docs/screenshots/skills-panel.png
       State:    Six starter-pack skills, cross-workspace-synthesis expanded

  4. Policy panel (cross-workspace + routing)
       URL:      ${WEB_URL}/  (Settings -> Policy tab)
       Filename: docs/screenshots/policy-panel.png
       State:    Two workspaces (acme-news + acme-user), one expanded with routing.yaml

  5. Audit log
       URL:      ${WEB_URL}/  (Settings -> Policy tab -> Audit log sub-tab)
       Filename: docs/screenshots/audit-log.png
       State:    Recent cross-workspace op entries visible

  6. Observability trace
       URL:      http://localhost:6006/   (Phoenix UI, if running)
                 or http://localhost:3001/ (Grafana from demo override)
       Filename: docs/screenshots/observability-trace.png
       State:    Most-recent trace expanded showing span tree + GenAI attributes

  7. Keyboard shortcuts overlay
       URL:      ${WEB_URL}/  (press Cmd+? or Ctrl+? to open overlay)
       Filename: docs/screenshots/keyboard-shortcuts-overlay.png
       State:    Overlay open showing all seven shortcuts grouped

Optional hero capture (viewport 2880x1800):

  H. Agent panel hero
       URL:      ${WEB_URL}/
       Filename: docs/screenshots/hero/agent-panel-with-multi-workspace@2x.png
       State:    Same as #1, plus the synthesis-engineering settings strip visible

$(color_bold "When done capturing:")
  1. Replace the placeholder PNGs in docs/screenshots/ with the real captures.
  2. Verify docs/release-notes-v3.4.0.md renders without broken-image icons.
  3. Compress with pngcrush or imageoptim before committing.
  4. Stop the stack: ./scripts/capture-screenshots.sh --stop

$(color_dim "Full procedure: docs/screenshots/CAPTURE.md")
EOF
}

main() {
  case "${1:-}" in
    --help|-h)
      usage
      ;;
    --stop)
      ensure_compose_available
      stop_demo_stack
      ;;
    --status)
      ensure_compose_available
      status_demo_stack
      ;;
    "")
      ensure_compose_available
      start_demo_stack
      print_capture_checklist
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
}

main "$@"
