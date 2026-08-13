"""通过 ctypes 调用 macOS Quartz 事件，无需 pyobjc / 编译器。"""

from __future__ import annotations

import ctypes
import time
from typing import Sequence

carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
core = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

# ---- 类型 ----
CGFloat = ctypes.c_double
CGEventRef = ctypes.c_void_p
CGEventSourceRef = ctypes.c_void_p


class CGPoint(ctypes.Structure):
    _fields_ = [("x", CGFloat), ("y", CGFloat)]


# 鼠标事件类型
kCGEventMouseMoved = 5
kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGEventRightMouseDown = 3
kCGEventRightMouseUp = 4
kCGEventOtherMouseDown = 25
kCGEventOtherMouseUp = 26
kCGEventScrollWheel = 22

kCGMouseButtonLeft = 0
kCGMouseButtonRight = 1
kCGHIDEventTap = 0

# 键盘
kCGEventKeyDown = 10
kCGEventKeyUp = 11
kCGEventFlagMaskCommand = 0x100000
kCGEventFlagMaskShift = 0x20000
kCGEventFlagMaskAlternate = 0x80000
kCGEventFlagMaskControl = 0x40000

# 常用 keycode（ANSI）
KEYCODE = {
    "a": 0,
    "s": 1,
    "d": 2,
    "f": 3,
    "h": 4,
    "g": 5,
    "z": 6,
    "x": 7,
    "c": 8,
    "v": 9,
    "b": 11,
    "q": 12,
    "w": 13,
    "e": 14,
    "r": 15,
    "y": 16,
    "t": 17,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "6": 22,
    "5": 23,
    "9": 25,
    "7": 26,
    "8": 28,
    "0": 29,
    "o": 31,
    "u": 32,
    "i": 34,
    "p": 35,
    "l": 37,
    "j": 38,
    "k": 40,
    "n": 45,
    "m": 46,
    "space": 49,
    "return": 36,
    "enter": 36,
    "tab": 48,
    "escape": 53,
    "esc": 53,
    "delete": 51,
    "backspace": 51,
    "command": 55,
    "cmd": 55,
    "shift": 56,
    "option": 58,
    "alt": 58,
    "control": 59,
    "ctrl": 59,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
}

MODIFIER_FLAGS = {
    "command": kCGEventFlagMaskCommand,
    "cmd": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "option": kCGEventFlagMaskAlternate,
    "alt": kCGEventFlagMaskAlternate,
    "control": kCGEventFlagMaskControl,
    "ctrl": kCGEventFlagMaskControl,
}

# 函数签名
core.CGEventCreate.argtypes = [CGEventSourceRef]
core.CGEventCreate.restype = CGEventRef

core.CGEventCreateMouseEvent.argtypes = [
    CGEventSourceRef,
    ctypes.c_uint32,
    CGPoint,
    ctypes.c_uint32,
]
core.CGEventCreateMouseEvent.restype = CGEventRef

core.CGEventCreateScrollWheelEvent.argtypes = [
    CGEventSourceRef,
    ctypes.c_uint32,  # units
    ctypes.c_uint32,  # wheel count
    ctypes.c_int32,  # wheel1
]
core.CGEventCreateScrollWheelEvent.restype = CGEventRef

core.CGEventCreateKeyboardEvent.argtypes = [
    CGEventSourceRef,
    ctypes.c_uint16,
    ctypes.c_bool,
]
core.CGEventCreateKeyboardEvent.restype = CGEventRef

core.CGEventSetFlags.argtypes = [CGEventRef, ctypes.c_uint64]
core.CGEventSetFlags.restype = None

core.CGEventSetIntegerValueField.argtypes = [CGEventRef, ctypes.c_uint32, ctypes.c_int64]
core.CGEventSetIntegerValueField.restype = None

core.CGEventPost.argtypes = [ctypes.c_uint32, CGEventRef]
core.CGEventPost.restype = None

core.CFRelease = core.CFRelease
core.CFRelease.argtypes = [ctypes.c_void_p]
core.CFRelease.restype = None

kCGScrollEventUnitLine = 1
kCGMouseEventClickState = 1  # event field


def _post(event: CGEventRef) -> None:
    if not event:
        raise RuntimeError("创建 CGEvent 失败，请检查「辅助功能」权限")
    core.CGEventPost(kCGHIDEventTap, event)
    core.CFRelease(event)


def move_to(x: int, y: int) -> None:
    point = CGPoint(float(x), float(y))
    event = core.CGEventCreateMouseEvent(None, kCGEventMouseMoved, point, kCGMouseButtonLeft)
    _post(event)


def click(x: int, y: int, button: str = "left") -> None:
    point = CGPoint(float(x), float(y))
    if button == "right":
        down_t, up_t, btn = kCGEventRightMouseDown, kCGEventRightMouseUp, kCGMouseButtonRight
    else:
        down_t, up_t, btn = kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGMouseButtonLeft
    down = core.CGEventCreateMouseEvent(None, down_t, point, btn)
    _post(down)
    time.sleep(0.02)
    up = core.CGEventCreateMouseEvent(None, up_t, point, btn)
    _post(up)


def double_click(x: int, y: int) -> None:
    point = CGPoint(float(x), float(y))
    for click_state in (1, 2):
        down = core.CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, kCGMouseButtonLeft)
        core.CGEventSetIntegerValueField(down, kCGMouseEventClickState, click_state)
        _post(down)
        time.sleep(0.02)
        up = core.CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, kCGMouseButtonLeft)
        core.CGEventSetIntegerValueField(up, kCGMouseEventClickState, click_state)
        _post(up)
        time.sleep(0.05)


def right_click(x: int, y: int) -> None:
    click(x, y, button="right")


def scroll(clicks: int) -> None:
    # clicks > 0 向上
    event = core.CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, int(clicks))
    _post(event)


def hotkey(keys: Sequence[str]) -> None:
    keys = [k.lower() for k in keys]
    modifiers = [k for k in keys if k in MODIFIER_FLAGS]
    normals = [k for k in keys if k not in MODIFIER_FLAGS]
    if not normals:
        raise ValueError(f"hotkey 缺少主键: {keys}")

    flags = 0
    for m in modifiers:
        flags |= MODIFIER_FLAGS[m]

    for key in normals:
        if key not in KEYCODE:
            raise ValueError(f"不支持的按键: {key}")
        code = KEYCODE[key]
        down = core.CGEventCreateKeyboardEvent(None, code, True)
        core.CGEventSetFlags(down, flags)
        _post(down)
        time.sleep(0.02)
        up = core.CGEventCreateKeyboardEvent(None, code, False)
        core.CGEventSetFlags(up, flags)
        _post(up)
