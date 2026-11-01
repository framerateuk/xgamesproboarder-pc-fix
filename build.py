#!/usr/bin/env python3
"""Build a ready-to-run X Games Pro Boarder folder for modern PCs from your own CD.

Usage:
  python3 build.py DISC.cue|DISC.ccd --dgvoodoo DGVOODOO.zip --ogg-winmm OGG-WINMM.zip [--out DIR] [--windows]

  DISC          your ESPN X Games Pro Boarder PC CD (Radical Entertainment / ESPN Digital Games / EA, 1998,
                BOARDER.EXE of 11 November 1998) as .cue + .bin or .ccd + .img, with its audio tracks
  --dgvoodoo    dgVoodoo2 2.79.3 zip (or its unpacked folder)
  --ogg-winmm   ogg-winmm release zip (or folder)
  --out         where to create XGamesProBoarder/ (default: this folder)
  --windows     a folder for Windows only: the same game/ folder, without the Steam Deck launch script

Needs Python 3.8+, ffmpeg and ffprobe on the PATH (they decode the Indeo 5 movies, which nothing on Windows 10/11
or Proton can play, so they are rewritten uncompressed), and an Ogg Vorbis encoder: oggenc (vorbis-tools) or
ffmpeg. Nothing from the game is in this repository: every game file comes from your disc.
"""
import argparse, concurrent.futures, hashlib, os, re, shutil, struct, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc, patch_exe, make_ctl, make_raw_avi

EXE_MD5 = "9bf5bb5419c4593c5608ce44ac92ff98"            # ROOT\BOARDER.EXE, 11 Nov 1998, "Version 35 Final"
PATCHED_MD5 = "483219da94a5167233ff38aa1b075e7c"
OGGWINMM_MD5 = "f4896addb8e4da30ebcfa2d9cc203c0e"       # winmm.dll of ogg-winmm v2025.01.16, the one tested
TRACKS = 10                                              # audio tracks 2-11


def md5(data): return hashlib.md5(data).hexdigest()


def encoder():
    if shutil.which("oggenc"): return lambda wav, ogg: ["oggenc", "-Q", "-q", "7", wav, "-o", ogg]
    if shutil.which("ffmpeg"):
        return lambda wav, ogg: ["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "7", ogg]
    sys.exit("needs oggenc (vorbis-tools) or ffmpeg on the PATH to encode the soundtrack")


def ccd_pregaps(path):
    """{track: INDEX 0 sector} from a CloneCD .ccd, so a track ends where the next one's pregap starts (as a .cue
    gives it; disc.py's .ccd reader ends it at the next INDEX 1)."""
    out, cur = {}, None
    for line in open(path, encoding="utf-8", errors="replace"):
        t = line.strip()
        m = re.match(r"\[TRACK (\d+)\]", t)
        if m: cur = int(m.group(1)); continue
        if t.startswith("["): cur = None; continue
        m = re.match(r"INDEX 0=(\d+)", t)
        if m and cur: out[cur] = int(m.group(1))
    return out


def rip(tracks, music, pregaps):
    """Each audio track from its INDEX 01 to the next track's INDEX 00 (the end of the disc for the last), as it is
    on the disc: the game plays a track from track:0:0:0 to its length (MCI TMSF) and moves on when the drive
    reports it stopped, so nothing is trimmed or padded."""
    enc = encoder(); os.makedirs(music, exist_ok=True); n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(tracks):
            if t.kind != "AUDIO": continue
            if i + 1 < len(tracks) and tracks[i + 1].n in pregaps: t.end = pregaps[tracks[i + 1].n]
            data = disc.audio(t)
            wav = os.path.join(tmp, f"track{t.n:02d}.wav"); ogg = os.path.join(music, f"Track{t.n:02d}.ogg")
            with open(wav, "wb") as o:
                o.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                        struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16) + b"data" +
                        struct.pack("<I", len(data)) + data)
            subprocess.run(enc(wav, ogg), check=True); os.remove(wav)
            print(f"  Music/Track{t.n:02d}.ogg  {len(data) / 176400:6.2f} s"); n += 1
    if n != TRACKS: sys.exit(f"expected {TRACKS} audio tracks (the game's music), found {n}: is the image missing them?")


def movies(dt, entries, out):
    """The disc's MOVIES\\*.AVI (Indeo 5) rewritten uncompressed by make_raw_avi.py, a few at a time."""
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool): sys.exit(f"needs {tool} on the PATH to rewrite the Indeo 5 movies")
    os.makedirs(out, exist_ok=True)
    names = sorted(k for k, (p, d, l, s) in entries.items()
                   if not d and k.startswith("MOVIES/") and k.endswith(".AVI") and k.count("/") == 1)
    with tempfile.TemporaryDirectory() as tmp:
        srcs = {}
        for k in names:                      # off the disc one at a time (one file handle), then decoded in parallel
            srcs[k] = os.path.join(tmp, k.split("/")[1]); dt.copy_file(*entries[k][2:], srcs[k])
        def one(k):
            make_raw_avi.main(srcs[k], os.path.join(out, k.split("/")[1])); os.remove(srcs[k])
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as ex:
            for f in [ex.submit(one, k) for k in names]: f.result()
    if len(names) != 8: sys.exit(f"expected the disc's 8 movies, found {len(names)}")


def take(src, member):
    """Bytes of the file whose path ends with `member` (case-insensitive) in a zip or folder."""
    want = member.lower()
    if os.path.isdir(src):
        for d, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(d, f)
                if os.path.relpath(p, src).replace(os.sep, "/").lower().endswith(want): return open(p, "rb").read()
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(want): return z.read(name)
    sys.exit(f"{member} not found in {src}")


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f: f.write(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("disc"); ap.add_argument("--dgvoodoo", required=True); ap.add_argument("--ogg-winmm", required=True)
    ap.add_argument("--out", default=HERE); ap.add_argument("--windows", action="store_true")
    a = ap.parse_args()

    tracks = disc.tracks(a.disc)
    pregaps = ccd_pregaps(a.disc) if a.disc.lower().endswith(".ccd") else {}
    data = [t for t in tracks if t.kind != "AUDIO"]
    if not data: sys.exit("no data track in " + a.disc)
    dt = disc.DataTrack(data[0])
    entries = {p.upper(): (p, is_dir, l, s) for p, is_dir, l, s in dt.walk()}
    if "ROOT/BOARDER.EXE" not in entries: sys.exit("no ROOT\\BOARDER.EXE on this CD: it isn't the X Games Pro Boarder PC disc")
    exe = dt.read_file(*entries["ROOT/BOARDER.EXE"][2:])
    if md5(exe) != EXE_MD5:
        sys.exit(f"this CD's BOARDER.EXE is not the 11 November 1998 exe the kit was made for (MD5 {md5(exe)}); "
                 "other versions aren't supported")

    pkg = os.path.join(os.path.abspath(a.out), "XGamesProBoarder"); game = os.path.join(pkg, "game")
    if os.path.exists(pkg): sys.exit(f"{pkg} already exists: move or delete it first")

    # What the installer's Typical install copies into its folder: the exe and its start-up data, the Pure3D
    # renderers in system\, Controls, Sound, Edison (menu music), Art, Movies and the tag file; the movie texture
    # filter (registered in Windows by the installer) sits beside the exe instead
    print("1/6 game files from the CD")
    one = {"ROOT/BOOT.PCB": "boot.pcb", "ROOT/BOOT.PCC": "boot.pcc", "ROOT/README/README.TXT": "readme.txt",
           "BOARDER.TAG": "boarder.tag", "DRIVERS/PDDID3DR.DLL": "system/pddid3dr.dll",
           "DRIVERS/PDDISFTR.DLL": "system/pddisftr.dll", "DRIVERS/RMVTXTMR.AX": "rmvtxtmr.ax"}
    for k, dst in one.items():
        dt.copy_file(*entries[k][2:], os.path.join(game, *dst.split("/")))
    for k, (p, is_dir, l, s) in entries.items():
        if not is_dir and k.split("/")[0] in ("ART", "SOUND", "EDISON", "CONTROLS"):
            dt.copy_file(l, s, os.path.join(game, *p.split("/")))
    write(os.path.join(game, "_spare", "boarder_retail.exe"), exe)
    ctl = dt.read_file(*entries["CONTROLS/10BUTTON.CTL"][2:])
    write(os.path.join(game, "_spare", "10BUTTON_disc.CTL"), ctl)

    print("2/6 exe patches and the pad layout")
    out = patch_exe.patch(exe, "boarder.exe")
    if md5(out) != PATCHED_MD5: sys.exit("patching gave an unexpected boarder.exe")
    write(os.path.join(game, "boarder.exe"), out)
    write(os.path.join(game, "CONTROLS", "10BUTTON.CTL"), make_ctl.ps(ctl))     # the PlayStation layout

    print("3/6 movies (Indeo 5 -> uncompressed; a few minutes, about 1.6 GB)")
    movies(dt, entries, os.path.join(game, "MOVIES"))

    print("4/6 soundtrack")
    rip(tracks, os.path.join(game, "Music"), pregaps)

    print("5/6 wrappers and settings")
    winmm = take(a.ogg_winmm, "winmm.dll")
    if md5(winmm) != OGGWINMM_MD5: print("  note: this isn't ogg-winmm v2025.01.16, the version tested")
    write(os.path.join(game, "winmm.dll"), winmm)
    write(os.path.join(game, "ddraw.dll"), take(a.dgvoodoo, "MS/x86/DDraw.dll"))
    write(os.path.join(game, "D3DImm.dll"), take(a.dgvoodoo, "MS/x86/D3DImm.dll"))
    for name in ("dgVoodoo.conf", "winmm.ini", "retrodeck.ini"):
        shutil.copyfile(os.path.join(HERE, "config", name), os.path.join(game, name))

    print("6/6 Steam Deck launch script" if not a.windows else "6/6 done")
    if not a.windows:
        launch = os.path.join(pkg, "xgpb_launch.sh")
        shutil.copyfile(os.path.join(HERE, "steamdeck", "xgpb_launch.sh"), launch); os.chmod(launch, 0o755)
    print(f"\ndone: {pkg}  (see README.md)")


if __name__ == "__main__":
    main()
