# crumb/ - the Crumb build

The machine in [Crumb](https://crumb.breadboard.cc/), the breadboard
simulator - the dress rehearsal before the real breadboards.
Current state: the clock module (`Computer.cru`) - a pot-tunable 555
astable plus a debounced manual pulse, both verified working.

`pull-from-crumb.sh` copies the .cru files from the Steam install into
this repo (safe direction). `push-to-crumb.sh` pushes them back into the
game - it refuses to run while CRUMB is open, so close the game first.
`--dry-run` shows what would move, in either script.

`Computer-Mike-Bushell.cru` is the CRUMB creator's own build of Ben
Eater's 8-bit computer - the authoritative
reference for the rest of the build; the video and the .cru download
are linked in the repo-level [Credits](../README.md#credits). His
clock module: astable = 1k + 50k + 1M pot + 1uF; debounce monostable
= 1M + 0.45uF.
