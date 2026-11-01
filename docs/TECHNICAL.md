# How it works

Notes on ESPN X Games Pro Boarder (Radical Entertainment / ESPN Digital Games / EA, Windows 95/98, 1998),
`ROOT\BOARDER.EXE` 963,072 bytes, PE time stamp 11 November 1998, Visual C++ 5, MD5
`9bf5bb5419c4593c5608ce44ac92ff98`. Addresses are virtual addresses in that exe; `patch_exe.py` holds each
patch, and the new code is assembled from `caves.s` into a 5th section `.xgpb` (VA `0x838000`).

## The disc

Track 1 is the data track (ISO 9660, volume `ProBoarder`); tracks 2-11 are the music (about 26 minutes).
The installer (InstallShield 5) copies, for a Typical install, `boarder.exe`, `boot.pcb` / `boot.pcc` (start-up
data), `Controls\`, `Sound\`, `Edison\` (menu music), `boarder.tag`, Radical's "Pure3D" renderers
(`DRIVERS\PDDID3DR.DLL` Direct3D, `PDDISFTR.DLL` software) into `system\`, `Art\` and `Movies\`; it registers
the movie texture filter `RMVTXTMR.AX` and the Indeo 5 codec in Windows and writes
`HKLM\SOFTWARE\ESPN Digital Games\Pro Boarder`. `build.py` copies the same folders, puts the filter beside the
exe, and leaves out the installer, DirectX 6, DirectX Media and the codecs.

## Settings and paths (noreg)

The settings reader (`0x47f410`) wanted the installer's values `Program Files`, `Art Files`, `Movie Files`,
`Src Files`, `CD-ROM`, `Movies Installed` ("Xgames Pro Boarder is not installed" without them). `noreg`: the
folders come from the exe's own location (+ `\ART`, `\MOVIES`), CD-ROM 0, Movies Installed 1. The `Graphics`
and `Input Devices` keys are still read and written by the game itself.

## CD test, CD music, first video mode (nocd, mode1024)

The CD test (`0x4717c0`) opened `boarder.tag` on the CD and checked it was a CD-ROM drive; `nocd` reports
that case at once, so CD music plays from track 2 through MCI (ogg-winmm). The game uses only MCI command
messages and polls the drive's mode for a track's end; no notification is waited for. `build.py` rips each
track from its INDEX 01 to the next track's INDEX 00, as on the disc.

The renderer DLLs list their 16-bit modes; on the first start the game took the first one, 320x200.
`mode1024`: 1024x768 (HUD art exists for 768 lines), else 640x480. The front end always runs at 640x480.
dgVoodoo2 2.79.3 (`ddraw.dll` + `D3DImm.dll`) runs the Direct3D renderer on Direct3D 11, 4:3, rendered at the
screen's size.

## Movies (radtex, findpin, skipkey; make_raw_avi.py)

The player is DirectShow: `RenderFile` the AVI, then a "RadMovie Texture Filter" (`rmvtxtmr.ax`) replaces the
Video Renderer so each frame is copied into a 16-bit surface and drawn by the 3D renderer. Three things stopped
it on modern systems:

- **Indeo 5**: no decoder on Windows 10/11 or in Wine; Proton decodes DirectShow video in GStreamer, which has
  none either. `make_raw_avi.py` rewrites the eight movies as uncompressed 24-bit BGR frames with 16-bit PCM,
  same sizes, rates and frame slots (ffmpeg decodes the Indeo).
- **Registration**: `radtex` tries `CoCreateInstance` first, then loads `rmvtxtmr.ax` from the game folder
  and uses its class factory. No registry, no admin rights.
- **The pin id**: the filter graph's "Video Renderer" was found by its input pin `"In"`, the pin id of
  DirectShow's original renderer; since Windows XP (and in Wine) the default renderer is the VMR, pin
  `VMR Input0`. `findpin` falls back to the renderer's first pin.

`skipkey`: the movie loop ended a movie only on cancel (Esc / B); accept (Enter / A) skips too.

## Sound (syncload, decodecb, sndwait)

DirectSound; the commentary banks and the menu music (MP3 in WAV) are decoded through ACM.

- `syncload`: the sound file loader picks its mode with `GetVersionExA`. Windows 95/98 got synchronous loads;
  on NT (Windows 2000 and later, Wine) it set up a loader "thread" that is a bare `ret` and left the
  synchronous flag as uninitialised `malloc` memory, so stream reads were dropped and a stream stayed "read in
  flight" for ever: the next stop of it (end of the menu music, end of a race) hung. Now every Windows takes
  the 95/98 branch.
- `decodecb`: a compressed read reported its completion only if its first chunk decoded to some output, and
  the later report depended on another uninitialised flag. Fraunhofer's 1998 MP3 codec always gave output;
  Wine's can give none for a short chunk, and the stream again waited for ever. The completion is now always
  reported, once.
- `sndwait`: four sound commands waited in `Sleep(10)` loops, inside a critical section, for the 16 ms timer
  callback that services the streams, while that callback needs the same section: a deadlock when the timing
  lines up. The waits now let the section go while they sleep.

## Exit (quit)

The exit path ended in `ExitProcess`, which runs every DLL's detach code (ogg-winmm, dgVoodoo, DirectShow),
where a hang under Proton leaves a black screen. `quit`: `TerminateProcess` after the same saving.

## Pad (pad10, pov, joyenum; make_ctl.py)

DirectInput, buffered. A pad gets a profile by name (Gravis, SideWinder) or by button count: 2, 4, 8 or exactly
10. An Xbox pad has 10 buttons on Windows and 10 or more under Wine; `pad10` takes 10 or more. `make_ctl.py`
writes `CONTROLS\10BUTTON.CTL` with the PlayStation version's layout by button position (the disc's in
`_spare\`); `--selftest` rebuilds every disc profile byte for byte. The game ignored the hat; `pov` turns the
D-pad into stick events. The triggers share the Z axis, so reverse camera is on both.

`joyenum`: on the Steam Deck Wine's DirectInput reader for the pad once stalled while holding the device lock,
so each `Poll` waited for a report and the game crawled. The joystick enumeration now runs only in pad mode:
`.\retrodeck.ini` `[Retrodeck] Pad=1` / `Pad=0` if present, otherwise off under Wine and on under Windows. The
kit ships `Pad=1`; with `Pad=0` the game reads only the keyboard and Steam Input sends keys.

## The race clock (qpc8)

The race clock used the *low dword* of `QueryPerformanceCounter`. Windows 95/98 counted at 1.19 MHz (an hour to
wrap); Wine and Windows 10/11 count at 10 MHz, so it wrapped every 429.5 s and a run crossing that moment
crawled at 1/30 speed. `qpc8` returns the 64-bit counter and frequency shifted right by 8: 30 hours to wrap.

## Frame pacing, cursor

A 16 ms multimedia timer drives the game; frames are presented with dgVoodoo's forced vertical sync, so there
is no busy wait to fix. The Windows cursor is hidden in full screen; the front end draws its own small pointer
for mouse use.
