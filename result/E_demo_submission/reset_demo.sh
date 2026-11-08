#!/usr/bin/env bash
# Reset the live demo in one command: fresh bundles in Supabase, a clean Yext sandbox entity, and the owner links.
#
#   ./result/E_demo_submission/reset_demo.sh                       # FI-D0017 (default)
#   ./result/E_demo_submission/reset_demo.sh FI-D0001 FI-D0017     # several businesses (all write to one Yext entity)
#   ./result/E_demo_submission/reset_demo.sh --dry-run             # show what would happen, change nothing
#   ./result/E_demo_submission/reset_demo.sh --yes                 # no confirmation prompt
#
# Reads the repo-root .env if it exists (variables already in the environment win). Needed:
#   SUPABASE_URL, SUPABASE_SERVICE_KEY, YEXT_API_KEY, YEXT_BASE_URL, LINK_SECRET, DEMO_CHAT_ID (Telegram chat of the owner)
# Optional: YEXT_ENTITY_ID (default SinceAI13), OWNER_APP_URL (default https://since-ai-porchlight.vercel.app),
#           NO_DOTENV=1 (do not read .env).
# Turn the n8n Scheduler off while recording, so no reminder lands in the chat.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DRY=0; YES=0; ENTITIES=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --yes|-y) YES=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) ENTITIES+=("$arg") ;;
  esac
done
[ ${#ENTITIES[@]} -eq 0 ] && ENTITIES=(FI-D0017)

if [ -f .env ] && [ "${NO_DOTENV:-0}" != "1" ]; then
  # keep variables that are already set in the environment
  while IFS='=' read -r key _; do
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [ -z "${!key:-}" ]; then set -a; eval "$(grep -E "^${key}=" .env | head -1)"; set +a; fi
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .env)
fi

YEXT_ENTITY_ID="${YEXT_ENTITY_ID:-SinceAI13}"
OWNER_APP_URL="${OWNER_APP_URL:-https://since-ai-porchlight.vercel.app}"
missing=()
for v in SUPABASE_URL SUPABASE_SERVICE_KEY YEXT_API_KEY YEXT_BASE_URL LINK_SECRET DEMO_CHAT_ID; do
  [ -n "${!v:-}" ] || missing+=("$v")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "error: set ${missing[*]} (in .env or the environment)" >&2; exit 2
fi

ONLY="$(IFS=,; echo "${ENTITIES[*]}")"
PY="${PYTHON:-python3}"
echo "Businesses: $ONLY · Yext entity: $YEXT_ENTITY_ID · app: $OWNER_APP_URL$([ $DRY = 1 ] && echo ' · DRY RUN')"

if [ $DRY = 0 ] && [ $YES = 0 ]; then
  read -r -p "This deletes ALL rows of decisions, apply_log, chat_sessions, bundle_items, bundles and clears the holiday hours of $YEXT_ENTITY_ID. Continue? [y/N] " ok
  [[ "$ok" =~ ^[Yy]$ ]] || { echo "cancelled"; exit 1; }
fi

DRYFLAG=(); [ $DRY = 1 ] && DRYFLAG=(--dry-run)

echo; echo "1/4 Build bundles (deterministic, from the frozen engine)"
"$PY" result/B_contact_decide/build_bundles.py | tail -1

echo; echo "2/4 Reload Supabase"
"$PY" result/B_contact_decide/load_to_supabase.py --reset --chat-id "$DEMO_CHAT_ID" --yext-entity "$YEXT_ENTITY_ID" \
  --only "$ONLY" ${DRYFLAG[@]+"${DRYFLAG[@]}"}

echo; echo "3/4 Clean the Yext sandbox entity"
"$PY" result/C_apply_yext/reset.py --entity "$YEXT_ENTITY_ID" ${DRYFLAG[@]+"${DRYFLAG[@]}"}

echo; echo "4/4 Owner links (no login)"
"$PY" result/B_contact_decide/owner_link.py "${ENTITIES[@]}" --base "$OWNER_APP_URL"

echo; echo "Done$([ $DRY = 1 ] && echo ' (dry run: nothing was changed)'). Next: run 'Connect · Step 3 Contact' in n8n to send the Telegram messages."
