#!/usr/bin/env bash
#
# sync-crumb.sh
# Copy CRUMB (.cru) circuit files between the Steam/Proton prefix and this repo.
#
# Usage:
#   ./sync-crumb.sh              pull  game -> repo
#   ./sync-crumb.sh --push       push  repo -> game   (close the game first!)
#   ./sync-crumb.sh --dry-run    show what would be copied, change nothing
#   ./sync-crumb.sh --delete     mirror exactly (remove repo files no longer in game)
#
set -euo pipefail

STEAM_APPID="2198800"

# Where CRUMB writes, inside the Proton prefix
PREFIX="${CRUMB_PREFIX:-$HOME/.local/share/Steam/steamapps/compatdata/$STEAM_APPID/pfx}"
SAVE_DIR="$PREFIX/drive_c/users/steamuser/Documents"

# Where the copies land
DEST="${CRUMB_REPO:-/home/nate/Projects/8bit-computer/crumb}"

DRY_RUN=0
PUSH=0
DELETE=0

for arg in "$@"; do
    case "$arg" in
    --dry-run | -n) DRY_RUN=1 ;;
    --push) PUSH=1 ;;
    --delete) DELETE=1 ;;
    -h | --help)
        grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed -n '1,11p'
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

if [[ $PUSH -eq 1 ]]; then
    SRC="$DEST/"
    TGT="$SAVE_DIR/"
    echo "pushing:  $DEST"
    echo "       -> $SAVE_DIR"
else
    SRC="$SAVE_DIR/"
    TGT="$DEST/"
    echo "pulling:  $SAVE_DIR"
    echo "       -> $DEST"
fi
echo

# ---- copy --------------------------------------------------------------------
if command -v rsync >/dev/null 2>&1; then
    rsync "${RSYNC_OPTS[@]}" "$SRC" "$TGT"
else
    echo "note: rsync not found, falling back to find+cp (flattens subfolders)"
    if [[ $PUSH -eq 1 ]]; then
        find "$DEST" -type f -iname '*.cru' -exec cp -v -- {} "$SAVE_DIR/" \;
    else
        find "$SAVE_DIR" -type f -iname '*.cru' -exec cp -v -- {} "$DEST/" \;
    fi
fi

# ---- summary -----------------------------------------------------------------
echo
if [[ $PUSH -eq 0 && $DRY_RUN -eq 0 ]]; then
    count=$(find "$DEST" -type f -iname '*.cru' | wc -l)
    echo "circuits now in $DEST: $count"
    find "$DEST" -type f -iname '*.cru' -printf '  %P\n'
fi
