# X Games Pro Boarder (BOARDER.EXE) code caves: the source of the bytes in patch_exe.py (docs/TECHNICAL.md).
#
#   python3 build_caves.py           assemble with clang (i686 ELF), print
#   python3 build_caves.py --write   the labels, compare with / rewrite
#                                                                        patch_exe.py
#
# Everything lives in a section patch_exe.py adds to the exe (".xgpb", the 5th section header, in the free
# header space at 0x248): VA 0x838000 (RVA 0x438000, right after .rsrc; section alignment 0x1000), raw data
# 0x1000 bytes appended at file offset 0xeb200 (the old end of the file), virtual size 0x2000, read/write/
# execute. The code starts at 0x838000; the variables sit at 0x839000, past the raw data, so they are zero at
# load. Targets in the original exe are written "A + (target - BASE)" so clang resolves them as plain rel32
# (no relocation); PUSHADDR label / ADDR label leave an R_386_32 relocation that build_caves.py adds BASE to.
#
# BOARDER.EXE is a Visual C++ 5 build: cdecl / thiscall (ecx = this), callee keeps ebx, esi, edi, ebp; the
# Win32 imports are stdcall (eax, ecx, edx clobbered).
#
# Imports (IAT slots): 0x4cb170 GetModuleFileNameA  0x4cb108 LoadLibraryA  0x4cb104 GetProcAddress
#   0x4cb130 GetCurrentProcess  0x4cb164 TerminateProcess  0x4cb334 CoCreateInstance (ole32)
#   0x4cb00c RegQueryValueExA  0x4cb000 RegCloseKey  0x4cb0c0 Sleep  0x4cb184 GetCurrentThreadId
#   0x4cb0d0 LeaveCriticalSection  0x4cb0d4 EnterCriticalSection  0x4cb16c GetModuleHandleA
#   0x4cb0f8 QueryPerformanceCounter  0x4cb0fc QueryPerformanceFrequency
# Game data: 0x4edcb0 the sound system's CRITICAL_SECTION (+8 RecursionCount, +0xc OwningThread = thread id)
# Game code: 0x451270 joystick axis event (thiscall: offset, value, time stamp, sequence)

.intel_syntax noprefix

.macro PUSHADDR lab               # push imm32 of a label (clang's intel mode makes "push offset" 16-bit)
    .byte 0x68
    .long \lab
.endm

.set PROG,     0x839000         # 0x110 bytes: the exe's folder, e.g. "Z:\home\deck\Self\XGamesProBoarder\game"
.set ART,      0x839110         # 0x110 bytes: PROG + "\ART"
.set MOV,      0x839220         # 0x110 bytes: PROG + "\MOVIES"
.set CF,       0x839330         # IClassFactory* of the movie texture filter (RADTEX)
.set PADM,     0x839334         # JOYENUM: 0 = not decided yet, 1 = pad on, 2 = pad off

.set BASE, 0x838000
.text
A:

#----------------------------------------------------------------------------------------------------
# NOREG (jumped to from 0x47f41b, the start of the registry reader 0x47f410, ecx = the settings block
# [0x4ed608]+0xf0): the installer's HKLM\SOFTWARE\ESPN Digital Games\Pro Boarder values are not read (the
# original returned 1, "XGames Pro Boarder is not installed", without them). The block gets what a full
# install would have written, built from the exe's own folder:
#   +0x00 Movies Installed = 1      +0x04 CD-ROM = 0 (no "CD-ROM required" check, 0x470041)
#   +0x44 Program Files = PROG      +0x48 Movie Files = PROG\MOVIES   +0x4c Art Files = PROG\ART
#   +0x50 Src Files = PROG (only read by the CD test, which patch nocd replaces)
# then on to the original's Graphics key part (0x47f65e: ebp = 0, esi = RegQueryValueExA, ebx = RegCloseKey,
# edi = the block, the stack as the original had it there).
NOREG:
    mov edi, ecx
    xor ebp, ebp
    push 0x104
    push PROG
    push 0
    call dword ptr [0x4cb170]       # GetModuleFileNameA(NULL, PROG, 260)
    mov ecx, PROG
    mov edx, ecx
1:  mov al, byte ptr [ecx]          # edx = the last backslash
    test al, al
    jz 2f
    cmp al, 0x5c
    jne 3f
    mov edx, ecx
3:  inc ecx
    jmp 1b
2:  mov byte ptr [edx], 0           # PROG = the folder, no trailing backslash
    mov esi, PROG
    mov ebx, ART
    call STRCPY
    PUSHADDR s_art
    pop esi
    call STRCPY
    mov esi, PROG
    mov ebx, MOV
    call STRCPY
    PUSHADDR s_mov
    pop esi
    call STRCPY
    mov dword ptr [edi], 1          # Movies Installed
    mov dword ptr [edi + 4], 0      # CD-ROM
    mov dword ptr [edi + 0x44], PROG
    mov dword ptr [edi + 0x48], MOV
    mov dword ptr [edi + 0x4c], ART
    mov dword ptr [edi + 0x50], PROG
    mov esi, dword ptr [0x4cb00c]   # RegQueryValueExA, as 0x47f448 set it
    mov ebx, dword ptr [0x4cb000]   # RegCloseKey, as 0x47f651
    jmp A + (0x47f65e - BASE)

# STRCPY: copy the string at esi to ebx (NUL included); ebx ends on the NUL. Clobbers al, esi.
STRCPY:
    mov al, byte ptr [esi]
    mov byte ptr [ebx], al
    test al, al
    jz 1f
    inc esi
    inc ebx
    jmp STRCPY
1:  ret

s_art: .asciz "\\ART"
s_mov: .asciz "\\MOVIES"

#----------------------------------------------------------------------------------------------------
# PICK (called from the first-run device choice 0x4713d0 at 0x471409, 0x47144c, 0x471487 in place of
# "first video mode of the device", eax = the chosen device): the device's mode list (sentinel at
# device+0x164, next pointer at +0, the game's mode number 0..6 at +0x10: 320x200, 320x240, 512x384, 640x400,
# 640x480, 800x600, 1024x768, from 0x47a600) -> the 1024x768 entry, else 640x480, else the first one, as
# before. Out: eax = the mode entry; every other register kept.
PICK:
    push ecx
    push edx
    lea ecx, [eax + 0x164]
    mov eax, dword ptr [ecx]
    mov edx, eax                    # default: the first entry (the original's choice)
1:  cmp eax, ecx
    je 3f
    cmp dword ptr [eax + 0x10], 6   # 1024x768
    je 2f
    cmp dword ptr [eax + 0x10], 4   # 640x480
    jne 4f
    mov edx, eax
4:  mov eax, dword ptr [eax]
    jmp 1b
2:  mov edx, eax
3:  mov eax, edx
    pop edx
    pop ecx
    ret

#----------------------------------------------------------------------------------------------------
# RADTEX (called from 0x48edb4 in place of CoCreateInstance, the movie player's "RadMovie Texture Filter",
# CLSID {cab185a0-d604-11d1-82e9-006097a78c47}, rmvtxtmr.ax, which renders the movie frames into a texture):
# the installer registered it (COM, Windows' system folder); here the registered one is tried first, then
# rmvtxtmr.ax from the game folder through its own DllGetClassObject: no registry, no admin rights.
# stdcall, the same five arguments (rclsid, outer, context, riid, ppv) and result as CoCreateInstance.
RADTEX:
    push ebp
    mov ebp, esp
    push dword ptr [ebp + 0x18]
    push dword ptr [ebp + 0x14]
    push dword ptr [ebp + 0x10]
    push dword ptr [ebp + 0xc]
    push dword ptr [ebp + 8]
    call dword ptr [0x4cb334]       # CoCreateInstance
    test eax, eax
    jge 9f
    PUSHADDR s_ax
    call dword ptr [0x4cb108]       # LoadLibraryA("rmvtxtmr.ax")
    test eax, eax
    jz 8f
    PUSHADDR s_dgco
    push eax
    call dword ptr [0x4cb104]       # GetProcAddress(, "DllGetClassObject")
    test eax, eax
    jz 8f
    push CF
    PUSHADDR iid_cf
    push dword ptr [ebp + 8]
    call eax                        # DllGetClassObject(rclsid, IID_IClassFactory, &CF)
    test eax, eax
    jl 9f
    mov ecx, dword ptr [CF]
    mov edx, dword ptr [ecx]
    push dword ptr [ebp + 0x18]
    push dword ptr [ebp + 0x14]
    push 0
    push ecx
    call dword ptr [edx + 0xc]      # IClassFactory::CreateInstance(NULL, riid, ppv)
    push eax
    mov ecx, dword ptr [CF]
    mov edx, dword ptr [ecx]
    push ecx
    call dword ptr [edx + 8]        # Release
    pop eax
    jmp 9f
8:  mov eax, 0x80040154             # REGDB_E_CLASSNOTREG, as before
9:  pop ebp
    ret 0x14

s_ax:   .asciz "rmvtxtmr.ax"
s_dgco: .asciz "DllGetClassObject"
iid_cf: .byte 0x01,0x00,0x00,0x00, 0x00,0x00, 0x00,0x00, 0xc0,0x00,0x00,0x00,0x00,0x00,0x00,0x46

#----------------------------------------------------------------------------------------------------
# FINDPIN (called from 0x48ee44 and 0x48ef78 in place of "mov edx, [eax]; push eax; call [edx+0x2c]", i.e.
# IBaseFilter::FindPin(this, L"In", &pin) on the graph's "Video Renderer"): the movie player takes the
# default video renderer's input pin to find the decoder's output, removes the renderer and renders that
# output again into the texture filter. "In" is the pin id of DirectShow's original 1996 Video Renderer;
# the default "Video Renderer" since Windows XP, and Wine's, is the VMR, whose pin is "VMR Input0", so
# FindPin failed and no movie played (seen in Wine 8 here). Now: FindPin as before, and if it fails the
# renderer's first pin (IBaseFilter::EnumPins, IEnumPins::Next; a video renderer has one, its input).
# stdcall, eax = this pushed by the caller site, then the original two arguments (id, ppPin) already pushed.
FINDPIN:
    push ebp
    mov ebp, esp
    push ebx
    push 0                          # [ebp-8] IEnumPins*
    mov ecx, dword ptr [ebp + 8]
    mov edx, dword ptr [ecx]
    push dword ptr [ebp + 0x10]
    push dword ptr [ebp + 0xc]
    push ecx
    call dword ptr [edx + 0x2c]     # FindPin(id, ppPin)
    test eax, eax
    jge 9f
    mov ecx, dword ptr [ebp + 8]
    mov edx, dword ptr [ecx]
    lea eax, [ebp - 8]
    push eax
    push ecx
    call dword ptr [edx + 0x28]     # EnumPins(&enum)
    test eax, eax
    jl 8f
    mov ecx, dword ptr [ebp - 8]
    mov edx, dword ptr [ecx]
    push 0
    push dword ptr [ebp + 0x10]
    push 1
    push ecx
    call dword ptr [edx + 0xc]      # IEnumPins::Next(1, ppPin, NULL)
    mov ebx, eax
    mov ecx, dword ptr [ebp - 8]
    mov edx, dword ptr [ecx]
    push ecx
    call dword ptr [edx + 8]        # Release
    mov eax, ebx
    test eax, eax
    je 9f                           # S_OK: the pin
8:  mov eax, 0x80040216             # VFW_E_NOT_FOUND, as FindPin
9:  add esp, 4
    pop ebx
    pop ebp
    ret 0xc

#----------------------------------------------------------------------------------------------------
# POV (jumped to from 0x451604, the joystick's buffered-event loop 0x451550, esi = the DIDEVICEOBJECTDATA,
# edi = the device): the original handled only the axes (offsets 0..0x1c) and buttons (0x30+); the hat
# (DIJOFS_POV(0) = 0x20: the Xbox pad's D-pad) did nothing. A hat event now becomes two axis events, X
# (offset 0) and Y (offset 4), at full deflection (+-0xffff, the range the game sets) or 0 when centred,
# through the game's own axis handler 0x451270: the D-pad steers and moves through menus like the stick.
# Directions: up 29250..6750, right 2250..15750, down 11250..24750, left 20250..33750 (hundredths of a
# degree, diagonals count both ways); centred = low word 0xffff.
POV:
    cmp dword ptr [esi], 0x20
    je 1f
    cmp dword ptr [esi], 0          # the original instruction (cmp [esi], 0 / jne 0x45161e)
    jne A + (0x45161e - BASE)
    jmp A + (0x451609 - BASE)
1:  push ebx
    mov eax, dword ptr [esi + 4]
    xor ebx, ebx                    # x
    xor edx, edx                    # y
    cmp ax, 0xffff
    je 5f
    cmp eax, 2250
    jb 2f
    cmp eax, 15750
    ja 2f
    mov ebx, 0xffff                 # right
2:  cmp eax, 20250
    jb 3f
    cmp eax, 33750
    ja 3f
    mov ebx, -0xffff                # left
3:  cmp eax, 6750
    jbe 31f
    cmp eax, 29250
    jb 4f
31: mov edx, -0xffff                # up
4:  cmp eax, 11250
    jb 5f
    cmp eax, 24750
    ja 5f
    mov edx, 0xffff                 # down
5:  push edx                        # y, kept for the second call
    push dword ptr [esi + 0xc]
    push dword ptr [esi + 8]
    push ebx
    push 0
    mov ecx, edi
    call A + (0x451270 - BASE)      # X event
    pop edx
    push dword ptr [esi + 0xc]
    push dword ptr [esi + 8]
    push edx
    push 4
    mov ecx, edi
    call A + (0x451270 - BASE)      # Y event
    pop ebx
    jmp A + (0x4516e2 - BASE)       # next event

#----------------------------------------------------------------------------------------------------
# Sound waits that deadlocked (seen on the Steam Deck: menu music plays on, the game hangs after a level is chosen).
# The sound commands run on the main thread inside the critical section 0x4edcb0 (0x467c65 .. 0x469d06); the
# streams and the file loader are serviced by the 16 ms multimedia-timer callback 0x471790 -> 0x465730, which
# takes the same critical section. Some commands wait, Sleep(10) at a time, for that service to move a stream
# or a read on: the stream stop 0x49f760 (state +0xd4 not 1 = no read in flight), 0x4a0d42 / 0x4a0d6f (another
# stream's +0xd0), the loader's synchronous read 0x4a168e (its completion flag). With the section held the
# timer thread blocks in EnterCriticalSection and the wait never ends (winedbg: main thread in 0x49f787 loop,
# owner of 0x4edcb0; timer thread at 0x46576f). Each of those Sleep(10) calls now goes through SLEEPCS, which
# lets the section go for the 10 ms if (and only if) this thread owns it, all recursion levels, and takes it
# back the same number of times: the timer service runs, the state moves, the wait ends. Called from a thread
# that does not own it (the timer thread itself, or code outside the section) it is the plain Sleep(10).
# Keeps every register but eax, ecx, edx (as Sleep).
SLEEPCS:
    push ebx
    push esi
    xor ebx, ebx                    # levels released
    call dword ptr [0x4cb184]       # GetCurrentThreadId
    cmp eax, dword ptr [0x4edcbc]   # OwningThread
    jne 2f
    mov esi, dword ptr [0x4edcb8]   # RecursionCount
    test esi, esi
    jz 2f
    mov ebx, esi
1:  push 0x4edcb0
    call dword ptr [0x4cb0d0]       # LeaveCriticalSection
    dec esi
    jnz 1b
2:  push 10
    call dword ptr [0x4cb0c0]       # Sleep(10)
    test ebx, ebx
    jz 4f
3:  push 0x4edcb0
    call dword ptr [0x4cb0d4]       # EnterCriticalSection
    dec ebx
    jnz 3b
4:  pop esi
    pop ebx
    ret

# WAITSTOP (jumped to from 0x49f7a7, "push 10; call edi (Sleep); jmp 0x49f78f" in the stream stop 0x49f760).
WAITSTOP:
    call SLEEPCS
    jmp A + (0x49f78f - BASE)

# WAITD0 (called from 0x4a0d50 and 0x4a0d79 in place of "push 10; call ebx (Sleep); cmp dword [esi], 0";
# the flags of the compare go back to the jne that follows).
WAITD0:
    call SLEEPCS
    cmp dword ptr [esi], 0
    ret

# WAITREAD (called from 0x4a168e in place of "push 10; call esi (Sleep); cmp [esp+0x18], edi", the loader's
# synchronous read waiting for its completion flag; one more dword on the stack here: the return address).
WAITREAD:
    call SLEEPCS
    cmp dword ptr [esp + 0x1c], edi
    ret

#----------------------------------------------------------------------------------------------------
# JOYENUM (called from 0x41d701 in place of the input set-up's joystick enumeration "mov eax, [esi]; push 1;
# push eax; push 0x41d600; push 4; push eax; mov edx, [eax]; call [edx+0x10]", IDirectInput::EnumDevices
# (DIDEVTYPE_JOYSTICK, 0x41d600, , DIEDFL_ATTACHEDONLY); esi = the input manager, [esi] = IDirectInput).
# Pad mode decides whether the game opens a joystick at all:
#   .\retrodeck.ini [Retrodeck] Pad=1 / Pad=0 if that key exists (GetPrivateProfileIntA), else
#   off under Wine / Proton (ntdll exports wine_get_version), on under Windows.
# Off: no joystick device, so Wine starts no HID reader for it; the game uses the keyboard, and on the Deck
# Steam Input turns the pad into keys. Why: on the Deck, the second run of a level: Wine's
# DirectInput reader thread sat in ReadFile on the pad's HID device while holding the device's lock, so every
# Poll (0x45155d) waited for the next HID report: one game frame every ~10 s (Wine's reads of the Deck's pad fail at
# random moments in some games; root cause in Wine).
JOYENUM:
    mov eax, dword ptr [PADM]
    test eax, eax
    jnz 5f
    PUSHADDR s_ini
    push -1
    PUSHADDR s_pad
    PUSHADDR s_sec
    PUSHADDR s_k32
    call dword ptr [0x4cb16c]       # GetModuleHandleA("kernel32.dll")
    PUSHADDR s_gpi
    push eax
    call dword ptr [0x4cb104]       # GetProcAddress(, "GetPrivateProfileIntA")
    call eax                        # GetPrivateProfileIntA("Retrodeck", "Pad", -1, ".\retrodeck.ini")
    cmp eax, -1
    je 1f
    test eax, eax
    jz 3f
    jmp 2f
1:  PUSHADDR s_ntdll
    call dword ptr [0x4cb16c]       # GetModuleHandleA("ntdll.dll")
    test eax, eax
    jz 2f
    PUSHADDR s_wine
    push eax
    call dword ptr [0x4cb104]       # GetProcAddress(, "wine_get_version")
    test eax, eax
    jnz 3f
2:  mov dword ptr [PADM], 1         # pad on
    jmp 5f
3:  mov dword ptr [PADM], 2         # pad off
5:  cmp dword ptr [PADM], 1
    jne 9f
    mov eax, dword ptr [esi]
    push 1
    push eax
    push 0x41d600
    push 4
    push eax
    mov edx, dword ptr [eax]
    call dword ptr [edx + 0x10]     # EnumDevices, as the original
9:  ret

s_k32:   .asciz "kernel32.dll"
s_gpi:   .asciz "GetPrivateProfileIntA"
s_sec:   .asciz "Retrodeck"
s_pad:   .asciz "Pad"
s_ini:   .asciz ".\\retrodeck.ini"
s_ntdll: .asciz "ntdll.dll"
s_wine:  .asciz "wine_get_version"

#----------------------------------------------------------------------------------------------------
# SKIPKEY (called from 0x454301 in place of "call 0x44e760", the movie loop's test of front-end action 5 with
# the arguments (5, 0) already pushed, ecx = the input manager [0x4ed608]+4): a movie ended early on action 5
# (cancel: Esc, pad B) or 6 (F12, which quits the game: 0x45433c tears everything down and sends WM_DESTROY). Now also on action 4 (accept: Enter, keypad
# Enter, pad A), so A / Enter skips as on a console; on the Deck A sends Space + Enter. thiscall, ret 8 as
# 0x44e760; result in ax (non-zero = pressed).
SKIPKEY:
    push ecx
    push 0
    push 5
    call A + (0x44e760 - BASE)      # cancel
    test ax, ax
    jnz 1f
    mov ecx, dword ptr [esp]
    push 0
    push 4
    call A + (0x44e760 - BASE)      # accept
1:  pop ecx
    ret 8

#----------------------------------------------------------------------------------------------------
# QPC8 / QPF8 (called from the game clock 0x82eea0's methods in place of QueryPerformanceCounter (0x479cf3,
# 0x479d1b, 0x479d5b) and QueryPerformanceFrequency (0x479ccb)): the clock keeps only the counter's low dword
# (start 0x479cfd, elapsed 0x479d21 / 0x479d61: low(now) - low(start) as an unsigned 32-bit count, divided by
# ticks per ms). Windows 95/98 counted at 1,193,182 Hz (the low dword wraps after an hour); Wine / Proton (and
# Windows 10/11) count at 10 MHz: the low dword wraps every 429.5 s, the clock jumps back, and a level running
# across that moment crawls (seen on the Deck, mid-run: level start at 277,331 ms, the clock now below
# it; the game clock frozen at 78.7 s, the race at 1/30 speed). Both now return the 64-bit values shifted right by
# 8 (10 MHz -> 39,062.5 Hz: the low dword wraps after 30 hours; 25.6 us resolution). stdcall, same result.
QPC8:
    push dword ptr [esp + 4]
    call dword ptr [0x4cb0f8]       # QueryPerformanceCounter
    jmp 1f
QPF8:
    push dword ptr [esp + 4]
    call dword ptr [0x4cb0fc]       # QueryPerformanceFrequency
1:  mov ecx, dword ptr [esp + 4]
    mov edx, dword ptr [ecx + 4]
    shrd dword ptr [ecx], edx, 8
    shr dword ptr [ecx + 4], 8
    ret 4

#----------------------------------------------------------------------------------------------------
# QUIT (called from 0x4715cb, the end of the exit path 0x4714f0, after the settings were written (0x47fd00)
# and every subsystem shut down): ExitProcess(0) -> TerminateProcess(GetCurrentProcess(), 0). ExitProcess
# also runs every DLL's detach code (ogg-winmm waits for its player thread, dgVoodoo, DirectShow), where a
# hang leaves the game on a black screen under Proton; nothing is left to save at this point.
QUIT:
    call dword ptr [0x4cb130]       # GetCurrentProcess
    push 0
    push eax
    call dword ptr [0x4cb164]       # TerminateProcess
    ret
