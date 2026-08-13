"""主屏逻辑尺寸（与鼠标坐标系一致）。"""

from __future__ import annotations

import ctypes
from typing import Tuple

core = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

CGDirectDisplayID = ctypes.c_uint32
CGFloat = ctypes.c_double


class CGPoint(ctypes.Structure):
    _fields_ = [("x", CGFloat), ("y", CGFloat)]


class CGSize(ctypes.Structure):
    _fields_ = [("width", CGFloat), ("height", CGFloat)]


class CGRect(ctypes.Structure):
    _fields_ = [("origin", CGPoint), ("size", CGSize)]


core.CGMainDisplayID.restype = CGDirectDisplayID
core.CGDisplayBounds.argtypes = [CGDirectDisplayID]
core.CGDisplayBounds.restype = CGRect


def main_display_logical_size() -> Tuple[int, int]:
    display = core.CGMainDisplayID()
    bounds = core.CGDisplayBounds(display)
    # CGDisplayBounds 返回的是全局点坐标下的逻辑尺寸
    return int(bounds.size.width), int(bounds.size.height)
