# ESPN X Games Pro Boarder (PC, 1998) on modern PCs and the Steam Deck

## Why this exists

We didn't get Cool Boarders on PC, or Steep Slope Sliders, and I remember seeing this in a shop as a kid and
begging my mum to buy it for me. She agreed pretty quickly given it was snowboarding and not Quake! Felt like
a proper grown-up boarding game, with a brilliant soundtrack and cool graphics. I was really pleased to get
this working again.

## What this does

Turns **your own** X Games Pro Boarder PC CD (Radical Entertainment / ESPN Digital Games, published by
EA, 1998) into a folder that runs on the Steam Deck (Proton) or on Windows 10/11, with no installer and no
registry entries made by an installer:

- **Copied straight from the CD**: what the installer's Typical install copied, so no CD is needed. The
  game takes its folders from where `boarder.exe` sits.
- **CD soundtrack** from OGG files ripped from your disc.
- **The movies play again**: the intro and bonus movies are Indeo 5, which neither Windows 10/11 nor
  Proton can decode, and the game's movie player relied on a filter the installer registered and on a
  video renderer pin that Windows XP and later don't have. The movies are rewritten uncompressed and the
  player is fixed.
- **No hangs**: the sound loader took a Windows 95/98-only branch (on anything newer it left reads
  unfinished, so the game froze when a race started or ended), four sound waits could deadlock, and an MP3
  chunk that decodes to nothing left the menu music waiting for ever. All fixed.
- **No slowdown after 7 minutes**: the race clock used half of a modern PC's timer, which wraps every
  7 minutes and turned a run into a slideshow.
- **Gamepad**: an Xbox-style pad (the Steam Deck's included) with the PlayStation version's layout,
  analogue steering and the D-pad; A skips movies.
- **1024x768 on the first start** instead of 320x200, and a quick exit.

**No game files are in this repository.** Everything from the game comes from your disc when you run
`build.py`.

## What you need

| | |
|---|---|
| The game | The **X Games Pro Boarder PC CD** (1998; `BOARDER.EXE` of 11 November 1998, "Version 35 Final") as `.cue` + `.bin` or CloneCD `.ccd` + `.img`, with its 10 audio tracks. `build.py` checks the exe and stops on another version. |
| Python | 3.8 or newer (python.org on Windows; already on macOS/Linux). |
| ffmpeg | `ffmpeg` and `ffprobe` on the PATH: they decode the Indeo 5 movies (Windows builds at ffmpeg.org). |
| An OGG encoder | `oggenc` (vorbis-tools; Windows builds at rarewares.org), or the same `ffmpeg`. |
| dgVoodoo2 **2.79.3** | by Dege: [GitHub release v2.79.3](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.79.3). Use 2.79.3: newer versions don't start under Wine/Proton. Keep the zip as downloaded. |
| ogg-winmm | by AyuanX: [GitHub releases](https://github.com/ayuanx/ogg-winmm/releases) (tested with v2025.01.16). Keep the zip as downloaded. |

## Build

```
python3 build.py XGamesProBoarder.cue --dgvoodoo dgVoodoo2_79_3.zip --ogg-winmm ogg-winmm_binary.zip
```

creates `XGamesProBoarder/` with `game/` and `xgpb_launch.sh` (for the Steam Deck), in a minute or two.
The movies take about 1.6 GB uncompressed. The same `game/` folder runs on Windows; `--windows` leaves
out the launch script. `--out DIR` puts the result somewhere else. The disc's original exe and pad
profile are kept in `game/_spare/`.

## Play on the Steam Deck

1. Copy `XGamesProBoarder/` to the Deck, for example to `/home/deck/Games/XGamesProBoarder/`.
2. Desktop Mode: Steam > Add a Non-Steam Game > Browse > `.../XGamesProBoarder/game/boarder.exe`. Rename
   the shortcut "X Games Pro Boarder".
3. Properties > Compatibility: force **Proton 9.0**. Pin it rather than floating on Experimental.
4. Properties > Launch Options:
   ```
   /home/deck/Games/XGamesProBoarder/xgpb_launch.sh %command%
   ```
5. Controller layout: the standard **Gamepad** layout. The game reads the pad itself
   (`game/retrodeck.ini` has `Pad=1`).

If the game ever crawls to a frame every few seconds during a long session, that's Wine's pad reader
stalling (it does in a few games). Switch the game to keys: set `Pad=0` in `game/retrodeck.ini` and give
the game a keyboard layout in Steam's controller settings:

| Deck | Key | Does |
|---|---|---|
| D-pad, left stick | arrow keys | menus; steer, speed up / slow down |
| A | Space and Enter | jump (hold to prepare a trick); choose in menus |
| B | Esc | back; pause |
| X | S | quick ollie, trick; pro grab |
| Y | D | 180 switch; pro grab |
| LB or LT / RB or RT | A / F | hard left / right; tricks |
| View (left) | C | change camera |
| Start (right) | Esc | pause |
| R3 | V | look back |

Steering is digital with keys.

## Play on Windows

Run `game/boarder.exe`. An Xbox pad works as on the Deck. The game keeps its graphics options and control
changes in the registry (`HKLM\Software\ESPN Digital Games\Pro Boarder`; Windows redirects that to your
user's VirtualStore), as it always did.

## Controls

The PlayStation version's layout, by button position (Cross = A, Circle = B, Square = X, Triangle = Y,
L1 / R1 = LB / RB, L2 = LT, Select = View):

| Pad | In the menus | Riding |
|---|---|---|
| D-pad or left stick | move | steer (analogue on the stick), speed up / slow down |
| A | choose | trick preparation (press, then the trick controls) |
| X | | quick ollie; in the air: trick 1 (amateur) / left-hand grab (pro) |
| B | the screen's extra function | 180 switch; in the air: trick 2 / right-hand grab |
| Y | back | in the air: trick 3 / third grab |
| LB / RB | | hard carve left / right (pro: adjust, rewind) |
| LT (or RT) | | reverse camera while held |
| View | | camera far / close / roaming |
| Start | back; skips a movie | pause / resume |

A, B and Start also skip a movie, one movie per press. The keyboard works as the game's Options >
Controls screen shows. F3 fog, F4 lens flares, F10 / F11 view size. Quit from the front end's exit icon
or Steam's Exit Game.

## Settings

- Resolution and detail: Options > Graphics in the game.
- 3D resolution, anti-aliasing, sharp pixels: `[DirectX] Resolution` (`max`, the kit's; `unforced`;
  `2x`), `Antialiasing`, `Resampling = pointsampled` in `game/dgVoodoo.conf`.
- Pad on or off: `[Retrodeck] Pad=1` / `Pad=0` in `game/retrodeck.ini` (without the file: off under
  Wine, on under Windows).
- Music level: `CDDAVolume` in `game/winmm.ini` (the in-game music slider may do nothing).
- Deck renderer: `RENDERER=wined3d` before the script path in the launch options uses Wine's own
  DirectDraw / Direct3D instead of dgVoodoo.

## Troubleshooting

- *"Xgames Pro Boarder is not installed"*: you're running the unpatched exe from `_spare/`.
- *Black screen or a crash at start*: `ddraw.dll`, `D3DImm.dll` and `dgVoodoo.conf` must sit beside
  `boarder.exe`.
- *No movies (straight to the language screen)*: `rmvtxtmr.ax` must sit beside `boarder.exe` and
  `MOVIES\` must hold the rewritten AVIs.
- *No music*: `game/Music/Track02.ogg` must exist beside `winmm.dll`; on the Deck `launch.log` must show
  `WINEDLLOVERRIDES=winmm=n,b;...` (no log: the launch option is missing `%command%`).
- *Judder on a G-Sync / FreeSync monitor*: turn variable refresh off for this game.

Tested on the Steam Deck (Proton 9.0) and on Windows 11.

## What's in this repository

| File | What |
|---|---|
| `build.py` | Builds the folder: copies the CD's game files, patches the exe, writes the pad profile, rewrites the movies, rips the soundtrack, adds the wrappers and settings. Python standard library plus ffmpeg. |
| `patch_exe.py` | The exe patches, each explained, with the new code's bytes; also runs on its own. |
| `caves.s`, `build_caves.py` | The source of that new code (x86 assembly) and the script that assembles it with clang into `patch_exe.py`. Only needed to change a patch. |
| `make_ctl.py` | Writes the pad profile `CONTROLS\10BUTTON.CTL` (the PlayStation layout); `--dump` lists a profile. |
| `make_raw_avi.py` | Rewrites one Indeo 5 movie as an uncompressed AVI. |
| `disc.py` | Reads the CD image: `.cue`/`.bin` or `.ccd`/`.img`, ISO 9660 and the audio tracks. |
| `config/` | dgVoodoo2's settings, ogg-winmm's, and `retrodeck.ini` (pad on). |
| `steamdeck/xgpb_launch.sh` | Proton launch wrapper: DLL overrides, logging. |
| `docs/TECHNICAL.md` | How the game works and what each patch does. |

## Credits

- **Radical Entertainment** made X Games Pro Boarder; **ESPN Digital Games** and **Electronic Arts**
  published it. Please own the game: this kit needs your disc.
- **Dege**: dgVoodoo2. **AyuanX**: ogg-winmm. **FFmpeg**: the Indeo 5 decoder.

## License

The scripts and docs in this repository: MIT (see `LICENSE`). The license covers only this
repository's own files, not the game, dgVoodoo2, ogg-winmm or ffmpeg.

Not affiliated with or endorsed by the game's rights holders.
