#!/usr/bin/env python3
"""Write X Games Pro Boarder's pad profile CONTROLS\\10BUTTON.CTL: the PlayStation version's layout on an Xbox pad
(docs/TECHNICAL.md).

  make_ctl.py <disc 10BUTTON.CTL> <out 10BUTTON.CTL>      write the Xbox layout
  make_ctl.py --dump <file.CTL>                           print a profile's bindings
  make_ctl.py --selftest <dir with the disc's *.CTL>      rebuild every disc profile byte for byte

A .CTL is a Pure3D-style chunk file: 00 fe, u32 file size, 6 header bytes (01 70 06 00 00 00), then three
chunks; a binding set is: u16 0xa973, u32 section size, u32 section id (0x0a2d67b4 front end, 0x0beb8024 amateur
riding, 0x04d9d5d4 professional riding; a small 0xb903 chunk between the riding sets is copied as it is), then an object at section+0x0c: u32 0, u32 count, a pointer to the
pointer array, count pointers, count entries of 4 u32 (action, 1, input code, mode); pointers are object
offsets tagged 0xea000000. Input codes (the game's DirectInput reader 0x451270 / 0x4511a0): 0x100 / 0x101
stick X left / right, 0x102 / 0x103 stick Y up / down (D-pad too, patch_exe.py pov), 0x104 / 0x105 Rz,
0x106 / 0x107 Z (the triggers' shared axis), 0x10b + n joystick button n. Mode 1 = on press, 0 = held, 2 = a
second player's copy (front end), 3 = keyboard-only entries (input 0).

The game picks a profile by the pad's name / product GUID (Microsoft and Gravis pads) or else by its button
count: 2, 4, 8 or 10 (patch_exe.py pad10: 10 or more) -> 10BUTTON.CTL. An Xbox pad through DirectInput
(Windows, Wine / Proton) has 10+ buttons: 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB, 6 Back / View, 7 Start / Menu,
8 L3, 9 R3; sticks X/Y and Rx/Ry, triggers on Z, the D-pad a POV hat.
"""
import struct, sys, os

A, B, X, Y, LB, RB, BACK, START, L3, R3 = (0x10b + n for n in range(10))
ZPOS, ZNEG = 0x106, 0x107            # the Z axis (an Xbox pad's triggers, shared): positive = LT, negative = RT
LEFT, RIGHT, UP, DOWN = 0x100, 0x101, 0x102, 0x103
IDS = (0x0a2d67b4, 0x0beb8024, 0x04d9d5d4)
HEAD = bytes.fromhex("017006000000")

def parse(d):
    assert d[:2] == b"\x00\xfe" and struct.unpack_from("<I", d, 2)[0] == len(d), "not a .CTL"
    p, secs = 12, []
    while p < len(d):
        tag, size, sid = struct.unpack_from("<HII", d, p)
        if tag != 0xa973:                         # other chunks (e.g. 0xb903 between the riding sets): kept as they are
            secs.append((None, d[p:p + size])); p += size; continue
        o = p + 0x0c
        zero, cnt, arr = struct.unpack_from("<III", d, o)
        ptrs = struct.unpack_from("<%dI" % cnt, d, o + 0x0c)
        ents = [struct.unpack_from("<4I", d, o + (q & 0xffffff)) for q in ptrs]
        secs.append((sid, ents)); p += size
    return secs

def build(secs):
    out = bytearray(b"\x00\xfe" + bytes(4) + HEAD)
    for sid, ents in secs:
        if sid is None:
            out += ents; continue
        n = len(ents)
        obj = struct.pack("<III", 0, n, 0xea000000 | 0x0c)
        base = 0x0c + 4 * n
        obj += b"".join(struct.pack("<I", 0xea000000 | (base + 16 * k)) for k in range(n))
        obj += b"".join(struct.pack("<4I", *e) for e in ents)
        sec = struct.pack("<HII", 0xa973, 0x0c + len(obj), sid) + b"\0\0" + obj
        out += sec
    struct.pack_into("<I", out, 2, len(out))
    return bytes(out)

def dump(path):
    for sid, ents in parse(open(path, "rb").read()):
        if sid is None:
            print("other chunk:", ents.hex()); continue
        print("section %08x: %d bindings" % (sid, len(ents)))
        for e in ents:
            print("   action %2x  %d  input %3x  mode %d" % e)

def ps(disc):
    """The PlayStation version's layout (from its manual), by button position on the Xbox / Deck pad:
    Cross = A, Circle = B, Square = X, Triangle = Y, L1 / R1 = LB / RB, L2 = LT, Select = View, Start = Start."""
    secs = parse(disc)
    fe, am, pro = [x for x in secs if x[0] is not None]
    keys = [e for e in pro[1] if e[3] == 3]          # the professional set's keyboard-only entries, as on the disc
    held = lambda act, *codes: [(act, 1, c, 0) for c in codes]
    press = lambda act, *codes: [(act, 1, c, 1) for c in codes]
    CROSS, CIRCLE, SQUARE, TRIANGLE, SELECT = A, B, X, Y, BACK
    ride = (held(0, LEFT) + held(1, RIGHT) + held(2, UP) + held(3, DOWN) + held(4, DOWN)
            + press(5, SELECT)            # camera far / close / roaming
            + held(6, ZPOS, ZNEG)         # reverse camera while held: L2 (LT; the triggers share Z, RT too)
            + held(7, LB) + held(8, RB)   # hard carve left / right (pro: adjust, rewind)
            + held(9, CIRCLE)             # 180 switch
            + press(10, START)            # pause / resume
            + held(11, CROSS)             # trick preparation (jump)
            + held(12, SQUARE))           # quick ollie
    amateur = ride + held(13, SQUARE) + held(14, CIRCLE) + held(15, TRIANGLE)   # tricks 1 / 2 / 3 in the air
    pro_ = (ride + held(15, SQUARE) + held(16, CIRCLE) + held(17, TRIANGLE)     # grabs: left hand / right hand / third
            + held(0x13, LEFT) + held(0x12, RIGHT) + held(0x14, UP) + held(0x15, DOWN) + keys)
    front = [(0, 1, LEFT, 1), (1, 1, RIGHT, 1), (2, 1, UP, 1), (3, 1, DOWN, 1),
             (0x16, 1, LEFT, 2), (0x17, 1, RIGHT, 2), (0x18, 1, UP, 2), (0x19, 1, DOWN, 2),
             (4, 1, CROSS, 1),            # select
             (5, 1, TRIANGLE, 1),         # cancel / previous menu
             (5, 1, START, 1),            # Start = the keyboard's Esc exactly (front-end cancel + riding pause, which
                                          # worked on the Deck): skips the current movie, pauses and
                                          # resumes a run; in menus it goes back. Never action 6 (the keyboard's F12):
                                          # a Start bound there quit the game in a run (and the movie loop
                                          # quits on it: 0x454327 -> 0x45433c)
             (7, 1, CIRCLE, 1)]           # the screen's extra button (video menu, defaults, biographies)
    new = {fe[0]: front, am[0]: amateur, pro[0]: pro_}
    return build([(sid, new[sid]) if sid is not None else (sid, ents) for sid, ents in secs])

def main(a):
    if len(a) == 2 and a[0] == "--dump":
        return dump(a[1])
    if len(a) == 2 and a[0] == "--selftest":
        for f in sorted(os.listdir(a[1])):
            if f.upper().endswith(".CTL"):
                d = open(os.path.join(a[1], f), "rb").read()
                print(f, "ok" if build(parse(d)) == d else "DIFFERS")
        return
    if len(a) != 2:
        sys.exit(__doc__)
    new = ps(open(a[0], "rb").read())
    open(a[1], "wb").write(new)
    print("wrote %s (%d bytes, PlayStation layout)" % (a[1], len(new)))

if __name__ == "__main__":
    main(sys.argv[1:])
