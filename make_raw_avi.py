#!/usr/bin/env python3
"""Rewrite one of X Games Pro Boarder's Indeo 5 movies as an uncompressed AVI (docs/TECHNICAL.md).

  make_raw_avi.py IN.AVI OUT.AVI

Video: 24-bit BGR DIB (BI_RGB, bottom-up, positive height), same size, same frame rate and the same
number of frame slots as the header of IN.AVI (each picture in its own slot, gaps repeat the previous
picture, the end padded); every frame is a key frame. Sound (if any): 16-bit PCM, same rate and channels,
interleaved one chunk per video frame. AVI 1.0 with an idx1 index.

Why uncompressed: the game plays its movies through DirectShow (quartz) into its own texture renderer
(rmvtxtmr.ax, which takes RGB555 / RGB565 only). Under Proton 9 every quartz path decodes video inside
GStreamer, whose Proton build has no Indeo (or Cinepak) decoder: it substitutes a placeholder. Raw RGB needs no decoder anywhere: GStreamer passes it through and
converts it to the 16-bit RGB the renderer asks for; on Windows the AVI Splitter hands it on and the Color
Space Converter makes the 16-bit RGB. 24-bit, not 16: GStreamer's riff code maps only 8/24/32-bit DIBs to
raw video ("Unhandled DIB RGB depth: 16").
Needs ffmpeg / ffprobe on PATH (ffmpeg decodes Indeo 5).
"""
import json, struct, subprocess, sys

def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", path],
                         check=True, capture_output=True).stdout
    return json.loads(out)["streams"]

def chunk(tag, data):
    pad = b"\0" if len(data) & 1 else b""
    return tag + struct.pack("<I", len(data)) + data + pad

def lst(tag, body):
    return b"LIST" + struct.pack("<I", len(body) + 4) + tag + body

def main(src, dst):
    streams = probe(src)
    v = next(s for s in streams if s["codec_type"] == "video")
    a = next((s for s in streams if s["codec_type"] == "audio"), None)
    w, h, n = int(v["width"]), int(v["height"]), int(v["nb_frames"])
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    if (w * 3) % 4: sys.exit(f"{src}: width {w} gives padded DIB rows")
    fsize = w * h * 3
    vf = f"fps=source_fps,tpad=stop_mode=clone:stop=60,trim=end_frame={n},vflip"   # vflip: DIB rows bottom-up
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-an", "-vf", vf, "-frames:v", str(n),
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], check=True, capture_output=True).stdout
    if len(raw) != n * fsize: sys.exit(f"{src}: got {len(raw) // fsize} frames, expected {n}")
    frames = [raw[i * fsize:(i + 1) * fsize] for i in range(n)]

    audio, rate, ch = b"", 0, 0
    if a:
        rate, ch = int(a["sample_rate"]), int(a["channels"])
        audio = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-vn", "-f", "s16le", "-acodec",
                                "pcm_s16le", "-ar", str(rate), "-ac", str(ch), "-"], check=True, capture_output=True).stdout
    align = 2 * ch if a else 0
    per = [0] * n                      # audio bytes after each video frame: exact running share, sample-aligned
    if a:
        for i in range(n):
            end = len(audio) if i == n - 1 else min(len(audio), (i + 1) * rate * den // num * align)
            per[i] = end

    movi, idx, pos, prev = [], [], 4, 0
    for i in range(n):
        c = chunk(b"00db", frames[i]); movi.append(c)
        idx.append(struct.pack("<4sIII", b"00db", 0x10, pos, fsize)); pos += len(c)
        if a and per[i] > prev:
            data = audio[prev:per[i]]; prev = per[i]
            c = chunk(b"01wb", data); movi.append(c)
            idx.append(struct.pack("<4sIII", b"01wb", 0x10, pos, len(data))); pos += len(c)
    movi = b"".join(movi)

    usec = round(1e6 * den / num)
    nstreams = 2 if a else 1
    avih = struct.pack("<14I", usec, fsize * num // den + rate * align, 0,
                       0x10, n, 0, nstreams, fsize, w, h, 0, 0, 0, 0)          # AVIF_HASINDEX
    bih = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, fsize, 0, 0, 0, 0)
    strh_v = struct.pack("<4s4sIHHIIIIIIIIhhhh", b"vids", b"\0\0\0\0", 0, 0, 0, 0, den, num, 0, n, fsize,
                         0xffffffff, 0, 0, 0, w, h)
    hdrl = chunk(b"avih", avih) + lst(b"strl", chunk(b"strh", strh_v) + chunk(b"strf", bih))
    if a:
        wfx = struct.pack("<HHIIHHH", 1, ch, rate, rate * align, align, 16, 0)
        strh_a = struct.pack("<4s4sIHHIIIIIIIIhhhh", b"auds", b"\0\0\0\0", 0, 0, 0, 0, 1, rate, 0,
                             len(audio) // align, rate * align, 0xffffffff, align, 0, 0, 0, 0)
        hdrl += lst(b"strl", chunk(b"strh", strh_a) + chunk(b"strf", wfx))
    body = b"AVI " + lst(b"hdrl", hdrl) + lst(b"movi", movi) + chunk(b"idx1", b"".join(idx))
    with open(dst, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(body)) + body)
    print(f"{dst}: {n} frames {w}x{h} BGR24" + (f", PCM {rate} Hz x{ch}, {len(audio) // align} samples" if a else ""))

if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
