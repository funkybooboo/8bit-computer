#!/usr/bin/env bash
#
# pull-from-crumb.sh
# Copy CRUMB (.cru) circuit files from the Steam/Proton prefix into this repo.
#
# Usage:
#   ./pull-from-crumb.sh            pull  game -> repo
#   ./pull-from-crumb.sh --dry-run  show what would be copied, change nothing
#   ./pull-from-crumb.sh --delete   mirror exactly (remove repo files no longer in game)
#
# The opposite direction (repo -> game) is push-to-crumb.sh.
#
set -euo pipefail

STEAM_APPID="2198800"

# Where CRUMB writes, inside the Proton prefix
PREFIX="${CRUMB_PREFIX:-$HOME/.local/share/Steam/steamapps/compatdata/$STEAM_APPID/pfx}"
SAVE_DIR="$PREFIX/drive_c/users/steamuser/Documents"

# Where the copies land
DEST="${CRUMB_REPO:-/home/nate/Projects/8bit-computer/crumb}"

DRY_RUN=0
DELETE=0

for arg in "$@"; do
    case "$arg" in
    --dry-run | -n) DRY_RUN=1 ;;
    --delete) DELETE=1 ;;
    -h | --help)
        grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed -n '2,10p'
        exit 0
        ;;
    *)
        echo "unknown option: $arg" >&2
        exit 2
        ;;
    esac
done

# ---- sanity checks -----------------------------------------------------------
if [[ ! -d "$SAVE_DIR" ]]; then
    echo "error: CRUMB save dir not found:" >&2
    echo "       $SAVE_DIR" >&2
    echo "Is CRUMB installed and has it been launched at least once?" >&2
    exit 1
fi

if pgrep -f 'CRUMB\.exe' >/dev/null 2>&1; then
    echo "warning: CRUMB looks like it is running - a circuit may be half-saved."
    echo "         close the game for a clean copy."
    echo
fi

mkdir -p "$DEST"

RSYNC_OPTS=(-a --prune-empty-dirs --include='*/' --include='*.cru' --exclude='*')
[[ $DRY_RUN -eq 1 ]] && RSYNC_OPTS+=(--dry-run)
[[ $DELETE -eq 1 ]] && RSYNC_OPTS+=(--delete)

echo "pulling:  $SAVE_DIR"
echo "       -> $DEST"
echo

# ---- copy --------------------------------------------------------------------
if command -v rsync >/dev/null 2>&1; then
    rsync "${RSYNC_OPTS[@]}" "$SAVE_DIR/" "$DEST/"
else
    echo "note: rsync not found, falling back to find+cp (flattens subfolders)"
    find "$SAVE_DIR" -type f -iname '*.cru' -exec cp -v -- {} "$DEST/" \;
fi

# ---- summary -----------------------------------------------------------------
echo
if [[ $DRY_RUN -eq 0 ]]; then
    count=$(find "$DEST" -type f -iname '*.cru' | wc -l)
    echo "circuits now in $DEST: $count"
    find "$DEST" -type f -iname '*.cru' -printf '  %P\n'
fi
