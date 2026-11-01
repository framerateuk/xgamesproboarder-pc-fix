#!/usr/bin/env python3
"""Patch X Games Pro Boarder's exe in place (the disc's ROOT\\BOARDER.EXE, 963,072 bytes,
MD5 9bf5bb5419c4593c5608ce44ac92ff98, linked 11 Nov 1998, Visual C++ 5).

  patch_exe.py game/BOARDER.EXE

Applies every patch not yet applied and reports each; refuses (writes nothing) on unexpected bytes.
docs/TECHNICAL.md has more on each one. The new code is in caves.s (build_caves.py
assembles it and checks it against CAVE / LABELS below), in a section this script adds (".xgpb").

  section  a 5th section, ".xgpb": header in the free header space at 0x248, VA 0x838000 (RVA 0x438000,
           virtual size 0x2000, read/write/execute), raw data (CAVE, 0x1000 bytes) appended at 0xeb200;
           NumberOfSections 4 -> 5, SizeOfImage 0x438000 -> 0x43a000.
  noreg    the settings reader 0x47f410 wanted the installer's HKLM\\SOFTWARE\\ESPN Digital Games\\Pro Boarder
           values (Program Files, Art Files, Movie Files, Src Files, CD-ROM, Movies Installed; without them:
           "XGames Pro Boarder is not installed"). 0x47f41b -> NOREG: the folders are the exe's own (+ \\ART,
           \\MOVIES), CD-ROM 0, Movies Installed 1; the Graphics key (written by the game) is read as before.
  nocd     the CD test 0x4717c0 (Src Files + "boarder.tag" must open and lie on a DRIVE_CDROM: CD music on,
           [settings+0x25c] = 1; else the music probe 0x4718e0) now reports the CD-ROM case at once: CD music
           from track 2 through MCI (ogg-winmm), no file or drive needed.
  mode1024 the first start (no Graphics key) chose the device's first video mode (320x200) at 0x471409,
           0x47144c, 0x471487; now PICK: 1024x768 (the game's largest; HUD art for it is on the disc), else
           640x480, else the first. Options > Graphics still changes it.
  radtex   the movie player's texture renderer (rmvtxtmr.ax, "RadMovie Texture Filter") was COM-registered
           by the installer; 0x48edb4 -> RADTEX: CoCreateInstance first, else the game folder's rmvtxtmr.ax
           through its DllGetClassObject.
  findpin  the player looks up the default video renderer's input pin by the id "In" (0x48ee44, 0x48ef78), the
           1996 Video Renderer's; the default renderer since Windows XP (and Wine's) is the VMR, "VMR Input0":
           no movie played. FINDPIN: FindPin as before, else the renderer's first pin (EnumPins).
  pad10    pads not known by name get a profile by button count, only 2, 4, 8 or exactly 10 (0x422bde):
           an Xbox pad under DirectInput has more (Wine), so it had none. Now 10 or more -> 10BUTTON.CTL
           (which make_ctl.py rewrites with an Xbox layout).
  pov      the joystick's buffered events (0x451550) ignored the hat: 0x451604 -> POV turns the D-pad into
           full X / Y stick deflections through the game's own axis handler 0x451270.
  syncload the sound file loader [0x4ee2c4] (0x4a1380) runs every request synchronously when its flag +0x34 is 0,
           which only the Windows 95/98 branch sets (0x4a140e, with a loader thread 0x4a28d0); on NT (Wine,
           Proton, Windows 2000+) +0x34 was left as malloc garbage and the "thread" was 0x49e460, a bare ret: with
           the flag set, stream reads (0x4a1ec0 & co.) went to 0x4a16b0, which drops them (loader +0x24 = 0) or
           posts them to the dead thread, so a stream stayed "read in flight" (+0xd4 = 1) for ever and the next
           stop of it waited for ever (seen on the Steam Deck: a hang going back to the menu after a run, the
           timer thread itself waiting in 0x49f760). 0x4a140c jne -> nop: every Windows takes the 95/98 branch, synchronous
           loads as the game always had there.
  decodecb a compressed (MP3 / ADPCM) stream read (0x4a1ec0) decodes its first chunk at once (0x4a23a0, ACM) and
           called the stream's completion back only if that chunk gave output (0x4a1ffd: size 0 -> no call);
           the decode pump 0x4a2840 calls back later only if the job's flag +0x24 is 0, which is never
           initialised (malloc, 0x4a1c77). Fraunhofer's codec always gave output; Wine's winemp3 can give
           none for a chunk (seen live: the last 2,919 bytes of EDISON\FE02.WAV, 0 bytes out), so the
           stream stayed "read in flight" (+0xd4 = 1) for ever and the next stop of it hung (intermittent:
           depends on where the chunks fall). Now always called back, and +0x24 set so the pump does not call
           a second time.
  sndwait  deadlock (seen on the Steam Deck: a hang after choosing a level, menu music playing on): sound commands run
           on the main thread inside the critical section 0x4edcb0, and four of them wait in Sleep(10) loops for
           the 16 ms timer callback (0x471790 -> 0x465730) to service a stream or a read, while that callback
           needs the same section. The waits (0x49f7a7 stream stop, 0x4a0d50 / 0x4a0d79 stream state, 0x4a168e
           loader read) now sleep through SLEEPCS: the section is let go for the 10 ms when this thread owns it.
  joyenum  pad mode: the input set-up's joystick enumeration (0x41d701, EnumDevices DIDEVTYPE_JOYSTICK) runs only
           in pad mode: .\\retrodeck.ini [Retrodeck] Pad=1/0 if present, else off under Wine (ntdll exports
           wine_get_version), on under Windows. On the Deck Wine's DirectInput reader for the pad once stalled
           in ReadFile holding the device lock, so each Poll waited for a HID report (one frame per ~10 s);
           with pad mode off the Deck gets keys through Steam Input instead (README).
  skipkey  the movie loop ended a movie only on front-end action 5 (cancel: Esc, pad B) or 6 (F12: quits the game) (0x454301);
           SKIPKEY also takes action 4 (accept: Enter, keypad Enter, pad A), so A skips on the Deck (Space +
           Enter through Steam Input) and on a Windows pad.
  qpc8     the game clock 0x82eea0 (0x479cc0 / 0x479d10 / 0x479d50) uses only the low dword of the performance
           counter: at Wine's (and Windows 10's) 10 MHz it wraps every 429.5 s and a level running across that
           crawls (seen on the Deck: a mid-run slideshow; Windows 95/98 counted at 1.19 MHz, an hour). QPC8 / QPF8 return
           the 64-bit counter and frequency shifted right by 8 (30 hours to wrap).
  quit     the exit path 0x4714f0 ended in ExitProcess(0) (0x4715cb; DLL detach code: ogg-winmm, dgVoodoo,
           DirectShow); now QUIT: TerminateProcess(GetCurrentProcess(), 0), after the same saving.
"""
import hashlib
import os
import sys

ORIG_SIZE, ORIG_MD5 = 963072, "9bf5bb5419c4593c5608ce44ac92ff98"
TEXT = 0x400c00                        # .text: VA 0x401000 at file offset 0x400
SEC_VA, SEC_RAW_OFF, SEC_RAW, SEC_VSIZE = 0x838000, 0xeb200, 0x1000, 0x2000

# caves.s, assembled by build_caves.py for VA 0x838000
CAVE = bytes.fromhex(
    "89cf31ed680401000068009083006a00ff1570b14c00b90090830089ca8a0184c074093c5c750289ca41ebf1c60200be"
    "00908300bb10918300e85f00000068aa8083005ee854000000be00908300bb20928300e84500000068af8083005ee83a"
    "000000c70701000000c7470400000000c7474400908300c7474820928300c7474c10918300c74750009083008b350cb0"
    "4c008b1d00b04c00e9c175c4ff8a06880384c074044643ebf4c35c415254005c4d4f564945530051528d88640100008b"
    "0189c239c8741483781006740c83781004750289c28b00ebea89c289d05a59c35589e5ff7518ff7514ff7510ff750cff"
    "7508ff1534b34c0085c07d5b685b818300ff1508b14c0085c07447686781830050ff1504b14c0085c074376830938300"
    "6879818300ff7508ffd085c07c298b0d309383008b11ff7518ff75146a0051ff520c508b0d309383008b1151ff520858"
    "eb05b8540104805dc21400726d767478746d722e617800446c6c476574436c6173734f626a6563740001000000000000"
    "00c0000000000000465589e5536a008b4d088b11ff7510ff750c51ff522c85c07d378b4d088b118d45f85051ff522885"
    "c07c218b4df88b116a00ff75106a0151ff520c89c38b4df88b1151ff520889d885c07405b81602048083c4045b5dc20c"
    "00833e20740e833e000f852f94c1ffe91594c1ff538b460431db31d26683f8ff744c3dca080000720c3d863d00007705"
    "bbffff00003d1a4f0000720c3dd68300007705bb0100ffff3d5e1a000076073d427200007205ba0100ffff3df22b0000"
    "720c3dae6000007705baffff000052ff760cff7608536a0089f9e81190c1ff5aff760cff7608526a0489f9e80090c1ff"
    "5be96c94c1ff535631dbff1584b14c003b05bcdc4e00751a8b35b8dc4e0085f6741089f368b0dc4e00ff15d0b04c004e"
    "75f26a0aff15c0b04c0085db740e68b0dc4e00ff15d4b04c004b75f25e5bc3e8b2ffffffe9c674c6ffe8a8ffffff833e"
    "00c3e89fffffff397c241cc3a13493830085c0756a689c8383006aff6898838300688e838300686b838300ff156cb14c"
    "00687883830050ff1504b14c00ffd083f8ff740685c0742deb1f68ac838300ff156cb14c0085c0741068b683830050ff"
    "1504b14c0085c0750cc7053493830001000000eb0ac7053493830002000000833d349383000175128b066a01506800d6"
    "41006a04508b10ff5210c36b65726e656c33322e646c6c004765745072697661746550726f66696c65496e7441005265"
    "74726f6465636b00506164002e5c726574726f6465636b2e696e69006e74646c6c2e646c6c0077696e655f6765745f76"
    "657273696f6e00516a006a05e88f63c1ff6685c0750c8b0c246a006a04e87e63c1ff59c20800ff742404ff15f8b04c00"
    "eb0aff742404ff15fcb04c008b4c24048b51040fac1108c1690408c20400ff1530b14c006a0050ff1564b14c00c3"
)
LABELS = {"NOREG": 0x838000, "STRCPY": 0x83809d, "s_art": 0x8380aa, "s_mov": 0x8380af, "PICK": 0x8380b7, "RADTEX": 0x8380e0, "s_ax": 0x83815b, "s_dgco": 0x838167, "iid_cf": 0x838179, "FINDPIN": 0x838189, "POV": 0x8381e1, "SLEEPCS": 0x838276, "WAITSTOP": 0x8382bf, "WAITD0": 0x8382c9, "WAITREAD": 0x8382d2, "JOYENUM": 0x8382dc, "s_k32": 0x83836b, "s_gpi": 0x838378, "s_sec": 0x83838e, "s_pad": 0x838398, "s_ini": 0x83839c, "s_ntdll": 0x8383ac, "s_wine": 0x8383b6, "SKIPKEY": 0x8383c7, "QPC8": 0x8383e6, "QPF8": 0x8383f2, "QUIT": 0x83840e}

def rel32(src, dst):                   # e8/e9 at src (5 bytes) -> dst
    return (dst - (src + 5)).to_bytes(4, "little", signed=True)

def jmp(src, label, pad=0):
    return b"\xe9" + rel32(src, LABELS[label]) + b"\x90" * pad

def call(src, label, pad=0):
    return b"\xe8" + rel32(src, LABELS[label]) + b"\x90" * pad

def u32(v):
    return v.to_bytes(4, "little")

# section header: ".xgpb", VirtualSize, RVA, raw size, raw offset, no relocs/lines,
# IMAGE_SCN_CNT_CODE | CNT_INITIALIZED_DATA | MEM_EXECUTE | MEM_READ | MEM_WRITE
SECHDR = b".xgpb\0\0\0" + u32(SEC_VSIZE) + u32(SEC_VA - 0x400000) + u32(SEC_RAW) + u32(SEC_RAW_OFF) + bytes(12) + u32(0xE0000060)

def patches():
    t = lambda va: va - TEXT
    return {
        "section":  [(0x248, bytes(40), SECHDR),
                     (0xb6, bytes.fromhex("0400"), bytes.fromhex("0500")),
                     (0x100, u32(0x438000), u32(0x43a000))],
        "noreg":    [(t(0x47f41b), bytes.fromhex("5033ed6a01"), jmp(0x47f41b, "NOREG"))],
        # mov eax, [0x4ed608]; mov ecx, [eax]; mov dword [ecx+0x25c], 1; mov eax, 1; ret
        "nocd":     [(t(0x4717c0), bytes.fromhex("51a108d64e00535657" "8b08bf183a4e0033c0c7815c0200"),
                      bytes.fromhex("a108d64e00" "8b08" "c7815c02000001000000" "b801000000" "c3"))],
        "mode1024": [(t(0x471409), bytes.fromhex("8b8064010000"), call(0x471409, "PICK", 1)),
                     (t(0x47144c), bytes.fromhex("8b90640100008a4210"), call(0x47144c, "PICK") + bytes.fromhex("8a4010") + b"\x90"),
                     (t(0x471487), bytes.fromhex("8b88640100008a5110"), call(0x471487, "PICK") + bytes.fromhex("8a5010") + b"\x90")],
        "radtex":   [(t(0x48edb4), bytes.fromhex("ff1534b34c00"), call(0x48edb4, "RADTEX", 1))],
        "findpin":  [(t(0x48ee44), bytes.fromhex("8b1050ff522c"), b"\x50" + call(0x48ee45, "FINDPIN")),
                     (t(0x48ef78), bytes.fromhex("8b1050ff522c"), b"\x50" + call(0x48ef79, "FINDPIN"))],
        "pad10":    [(t(0x422bdb), bytes.fromhex("83f90a753a"), bytes.fromhex("83f90a7c3a"))],
        "pov":      [(t(0x451604), bytes.fromhex("833e007515"), jmp(0x451604, "POV"))],
        "syncload": [(t(0x4a140c), bytes.fromhex("7516"), bytes.fromhex("9090"))],
        "decodecb": [(t(0x4a1ffd), bytes.fromhex("8b0785c07409"), bytes.fromhex("804824019090"))],   # or byte [eax+0x24], 1
        "sndwait":  [(t(0x49f7a7), bytes.fromhex("6a0affd7ebe2"), jmp(0x49f7a7, "WAITSTOP", 1)),
                     (t(0x4a0d50), bytes.fromhex("6a0affd3833e00"), call(0x4a0d50, "WAITD0", 2)),
                     (t(0x4a0d79), bytes.fromhex("6a0affd3833e00"), call(0x4a0d79, "WAITD0", 2)),
                     (t(0x4a168e), bytes.fromhex("6a0affd6397c2418"), call(0x4a168e, "WAITREAD", 3))],
        "joyenum":  [(t(0x41d701), bytes.fromhex("8b066a015068 00d64100 8b106a0450ff5210".replace(" ", "")), call(0x41d701, "JOYENUM", 13))],
        "skipkey":  [(t(0x454301), bytes.fromhex("e85aa4ffff"), call(0x454301, "SKIPKEY"))],
        "qpc8":     [(t(0x479ccb), bytes.fromhex("ff15fcb04c00"), call(0x479ccb, "QPF8", 1)),
                     (t(0x479cf3), bytes.fromhex("ff15f8b04c00"), call(0x479cf3, "QPC8", 1)),
                     (t(0x479d1b), bytes.fromhex("ff15f8b04c00"), call(0x479d1b, "QPC8", 1)),
                     (t(0x479d5b), bytes.fromhex("ff15f8b04c00"), call(0x479d5b, "QPC8", 1))],
        "quit":     [(t(0x4715cb), bytes.fromhex("6a00ff15f0b04c00"), call(0x4715cb, "QUIT", 3))],
    }

def patch(data, path="BOARDER.EXE"):
    """Returns `data` (the disc's exe, or one already patched by this script) with every patch applied; exits
    (nothing written) on unexpected bytes."""
    data = bytearray(data)
    raw = CAVE + bytes(SEC_RAW - len(CAVE))
    assert len(CAVE) <= SEC_RAW
    if len(data) == ORIG_SIZE:
        if hashlib.md5(data).hexdigest() != ORIG_MD5:
            sys.exit(f"{path}: not the disc's BOARDER.EXE (MD5 {ORIG_MD5}); nothing written")
        tail = "old"
    elif len(data) == ORIG_SIZE + SEC_RAW and data[ORIG_SIZE:] == raw:
        tail = "new"
    else:
        sys.exit(f"{path}: {len(data)} bytes, expected {ORIG_SIZE} (or patched: {ORIG_SIZE + SEC_RAW}); nothing written")
    todo = []
    for name, sites in patches().items():
        state = set()
        for off, old, new in sites:
            assert len(old) == len(new), name
            cur = bytes(data[off:off + len(new)])
            state.add("new" if cur == new else "old" if cur == old else "bad")
        if name == "section":
            state.add(tail)
        if state == {"new"}:
            print(f"  {name:9s} already applied"); continue
        if state != {"old"}:
            sys.exit(f"{path}: {name} has unexpected bytes ({sorted(state)}); not this exe? nothing written")
        todo.append(name)
    for name in todo:
        for off, old, new in patches()[name]:
            data[off:off + len(new)] = new
        if name == "section":
            data += raw
        print(f"  {name:9s} applied")
    return bytes(data)

def main(path):
    out = patch(open(path, "rb").read(), path)
    tmp = path + ".tmp"
    open(tmp, "wb").write(out)
    os.replace(tmp, path)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
