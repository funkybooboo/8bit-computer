#!/usr/bin/env bash
#
# push-to-crumb.sh
# Push .cru circuit files from this repo INTO the CRUMB Steam/Proton install.
# Overwrites the game's copies - refuses to run while CRUMB is open.
#
# Usage:
#   ./push-to-crumb.sh            push  repo -> game   (close the game first!)
#   ./push-to-crumb.sh --dry-run  show what would be copied, change nothing
#
set -euo pipefail

STEAM_APPID="2198800"

# Where CRUMB writes, inside the Proton prefix
PREFIX="${CRUMB_PREFIX:-$HOME/.local/share/Steam/steamapps/compatdata/$STEAM_APPID/pfx}"
SAVE_DIR="$PREFIX/drive_c/users/steamuser/Documents"

# Where the repo copies live
SRC="${CRUMB_REPO:-/home/nate/Projects/8bit-computer/crumb}"

DRY_RUN=0

for arg in "$@"; do
    case "$arg" in
    --dry-run | -n) DRY_RUN=1 ;;
    -h | --help)
        grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed -n '2,8p'
        exit 0
        ;;
    *)
        echo "unknown option: $arg" >&2
        exit 2
        ;;
    esac
done

# ---- sanity checks -----------------------------------------------------------
# Pushing while the game is up would clobber a live save (and the game may
# rewrite the file on exit anyway), so make this a hard error, not a warning.
if pgrep -f 'CRUMB\.exe' >/dev/null 2>&1; then
    echo "error: CRUMB is running - a push now would clobber the game's live save." >&2
    echo "       Close CRUMB completely, then re-run." >&2
    exit 1
fi

if [[ ! -d "$SAVE_DIR" ]]; then
    echo "error: CRUMB save dir not found:" >&2
    echo "       $SAVE_DIR" >&2
    echo "Is CRUMB installed and has it been launched at least once?" >&2
    exit 1
fi

if ! compgen -G "$SRC/*.cru" >/dev/null; then
    echo "error: no .cru files found in $SRC - nothing to push." >&2
    exit 1
fi

# ---- copy --------------------------------------------------------------------
echo "pushing:  $SRC"
echo "       -> $SAVE_DIR"
echo

RSYNC_OPTS=(-a --prune-empty-dirs --include='*/' --include='*.cru' --exclude='*')
[[ $DRY_RUN -eq 1 ]] && RSYNC_OPTS+=(--dry-run)

# No --delete here on purpose: never remove circuits that exist only in the game.
if command -v rsync >/dev/null 2>&1; then
    rsync "${RSYNC_OPTS[@]}" "$SRC/" "$SAVE_DIR/"
else
    echo "note: rsync not found, falling back to find+cp (flattens subfolders)"
    find "$SRC" -type f -iname '*.cru' -exec cp -v -- {} "$SAVE_DIR/" \;
fi

echo
echo "done. Launch CRUMB and open the circuit to verify."
