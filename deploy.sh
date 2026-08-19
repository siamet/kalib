#!/usr/bin/env bash
#
# Sync working-tree code to the Windows instrument machine.
#
# For the fast development loop: pushes uncommitted work without needing
# a commit. Use git for checkpoints you want to keep.
#
# Configure with environment variables (or a .env.deploy file):
#   KALIB_HOST     ssh target for the instrument machine, e.g. eng@192.168.1.40
#   KALIB_PATH     destination directory on that machine
#   KALIB_RESTART  optional command run over ssh after syncing
#
# Usage:
#   ./deploy.sh            sync, then restart if KALIB_RESTART is set
#   ./deploy.sh --dry-run  show what would transfer, change nothing

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
[ -f .env.deploy ] && . ./.env.deploy

: "${KALIB_HOST:?set KALIB_HOST (e.g. export KALIB_HOST=eng@192.168.1.40)}"
: "${KALIB_PATH:=/c/kalib}"

DRY=()
[ "${1:-}" = "--dry-run" ] && DRY=(--dry-run) && echo "DRY RUN - nothing will be written"

# config/config.yaml is deliberately absent: it holds the instrument's own
# device IDs and serial port, and must never be overwritten from here.
rsync -az --delete "${DRY[@]}" \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.venv/' \
  --exclude 'logs/' \
  --exclude 'data/' \
  --itemize-changes \
  kalib/ "$KALIB_HOST:$KALIB_PATH/kalib/"

rsync -az "${DRY[@]}" --itemize-changes \
  config/default_config.yaml requirements.txt .python-version \
  "$KALIB_HOST:$KALIB_PATH/"

if [ -n "${KALIB_RESTART:-}" ] && [ ${#DRY[@]} -eq 0 ]; then
  echo "restarting: $KALIB_RESTART"
  ssh "$KALIB_HOST" "$KALIB_RESTART"
fi

echo "synced to $KALIB_HOST:$KALIB_PATH"
