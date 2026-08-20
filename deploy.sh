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
# The instrument machine runs stock Windows OpenSSH, which ships scp but not
# rsync, so fall back when rsync is unavailable on either end. scp cannot
# delete files that were removed locally - stale .py files linger and cause
# confusing failures - so the fallback warns rather than pretending parity.
if rsync --version >/dev/null 2>&1 && ssh "$KALIB_HOST" "where rsync" >/dev/null 2>&1; then
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
else
  echo "rsync unavailable on one end; falling back to scp."
  echo "NOTE: scp does not delete files removed locally - if you deleted or"
  echo "      renamed a module, remove its stale copy on the target by hand."
  if [ ${#DRY[@]} -ne 0 ]; then
    echo "DRY RUN: would scp kalib/, config/default_config.yaml, requirements.txt, .python-version"
  else
    tar --exclude='__pycache__' --exclude='*.pyc' -cf - kalib \
      | ssh "$KALIB_HOST" "cd $KALIB_PATH && tar -xf -" \
      || { echo "tar-over-ssh failed; is tar available on the target?"; exit 1; }
    # scp does not preserve the source's directory structure the way rsync
    # does, so name each destination explicitly or default_config.yaml lands
    # in the repo root instead of config/.
    scp -q config/default_config.yaml "$KALIB_HOST:$KALIB_PATH/config/default_config.yaml"
    scp -q requirements.txt .python-version "$KALIB_HOST:$KALIB_PATH/"
  fi
fi

if [ -n "${KALIB_RESTART:-}" ] && [ ${#DRY[@]} -eq 0 ]; then
  echo "restarting: $KALIB_RESTART"
  ssh "$KALIB_HOST" "$KALIB_RESTART"
fi

echo "synced to $KALIB_HOST:$KALIB_PATH"
