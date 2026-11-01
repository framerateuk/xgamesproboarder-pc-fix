#!/bin/bash
# X Games Pro Boarder (Radical Entertainment / ESPN Digital Games, PC 1998) Steam Deck / Proton launch wrapper.
#
# Steam > X Games Pro Boarder > Properties > Launch Options:
#   /home/deck/Games/XGamesProBoarder/xgpb_launch.sh %command%
# Shortcut target: /home/deck/Games/XGamesProBoarder/game/boarder.exe, Start In: /home/deck/Games/XGamesProBoarder/game/
#
# boarder.exe is patched (patch_exe.py): the installer's registry values are made up from the exe's own folder,
# no CD test (CD music from track 2 through MCI, i.e. ogg-winmm), 1024x768 on the first start, the movie
# texture filter (rmvtxtmr.ax) loaded from the game folder and found behind the modern video renderer, Xbox
# pad profile by button count and D-pad (game/retrodeck.ini [Retrodeck] Pad=1, as built: the game reads the pad;
# Pad=0: keys only, sent by a Steam Input keyboard layout), quit without the DLL teardown. No fake CD-ROM drive.
# Settings the game writes: HKLM\Software\ESPN Digital Games\Pro Boarder\Graphics and \Input Devices in the
# Proton prefix (graphics options, control bindings), the career save game/PROBOARD.sav.
#
# Every launch sets DLL overrides so Wine loads the wrappers sitting beside the exe:
#   winmm.dll   ogg-winmm: CD audio from Music/Track02..11.ogg
#   ddraw.dll   dgVoodoo2 2.79.3: DirectDraw + Direct3D (with d3dimm.dll) -> D3D11 -> DXVK, 4:3 on the screen
#
# RENDERER (set before the script path in Launch Options, or a file RENDERER beside this script, default dgvoodoo):
#   dgvoodoo  ddraw + d3dimm from dgVoodoo2
#   wined3d   plain Wine ddraw / Direct3D
# XGPB_ARGS (or a file XGPB_ARGS beside this script): extra switches for boarder.exe (none are needed).

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HERE/launch.log"
[ -z "${RENDERER:-}" ] && [ -s "$HERE/RENDERER" ] && RENDERER="$(tr -d ' \n' < "$HERE/RENDERER")"
RENDERER="${RENDERER:-dgvoodoo}"
[ -z "${XGPB_ARGS:-}" ] && [ -s "$HERE/XGPB_ARGS" ] && XGPB_ARGS="$(tr '\n' ' ' < "$HERE/XGPB_ARGS")"
XGPB_ARGS="${XGPB_ARGS:-}"
log() { echo "[$(date '+%H:%M:%S')] $*" >>"$LOG"; }
: >"$LOG"
log "args: $*"
log "RENDERER=$RENDERER  XGPB_ARGS=$XGPB_ARGS  STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-unset}"

# Proton appends its own overrides after ours.
OVR="winmm=n,b"
case "$RENDERER" in
  dgvoodoo) OVR="$OVR;ddraw=n,b;d3dimm=n,b" ;;
  wined3d)  OVR="$OVR;ddraw=b;d3dimm=b" ;;
  *)        log "unknown RENDERER '$RENDERER', using dgvoodoo"; OVR="$OVR;ddraw=n,b;d3dimm=n,b" ;;
esac
export WINEDLLOVERRIDES="${OVR}${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
log "WINEDLLOVERRIDES=$WINEDLLOVERRIDES"

# Debugging: if a file named PROTON_LOG exists beside this script, Proton writes
# steam-<appid>.log here (crash addresses, exceptions). Create / delete it from Desktop Mode; no launch-option edit.
if [ -e "$HERE/PROTON_LOG" ]; then
  export PROTON_LOG=1 PROTON_LOG_DIR="$HERE"
  log "PROTON_LOG on -> $HERE/steam-*.log"
  # Extra Wine debug channels for that log: a file WINEDEBUG beside this script holding e.g. +quartz,+dinput
  if [ -s "$HERE/WINEDEBUG" ]; then
    export WINEDEBUG="+timestamp,+tid,+seh,+loaddll,$(tr -d ' \n' < "$HERE/WINEDEBUG")"
    log "WINEDEBUG=$WINEDEBUG"
  fi
fi

# Frame rate / GPU load overlay (DXVK, on top of dgVoodoo's D3D11): a file DXVK_HUD beside this script
# holding e.g. fps,gpuload. Create / delete it from Desktop Mode.
if [ -s "$HERE/DXVK_HUD" ]; then
  export DXVK_HUD="$(tr -d ' \n' < "$HERE/DXVK_HUD")"
  log "DXVK_HUD=$DXVK_HUD"
fi

for f in boarder.exe boot.pcb boot.pcc system/pddid3dr.dll system/pddisftr.dll rmvtxtmr.ax CONTROLS/10BUTTON.CTL \
         ART/GFE/COMMON.P3D SOUND/VXM.WAP EDISON/FE01.WAV MOVIES/INTR.AVI winmm.dll winmm.ini ddraw.dll D3DImm.dll \
         dgVoodoo.conf Music/Track02.ogg Music/Track11.ogg; do
  [ -e "$HERE/game/$f" ] || log "WARNING: game/$f missing"
done

# shellcheck disable=SC2086
log "exec: $* $XGPB_ARGS"
exec "$@" $XGPB_ARGS
