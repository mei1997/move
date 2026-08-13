"""运行环境检测与执行策略选择。"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass
from enum import Enum


class PlatformKind(str, Enum):
    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    UNKNOWN = "unknown"


class ExecStrategy(str, Enum):
    """桌面操控后端策略。"""

    # macOS：优先无障碍树按名字点控件，失败再截屏+像素点击
    ACCESSIBILITY_FIRST = "accessibility_first"
    # 仅截屏 + 视觉模型 + 键鼠（通用兜底）
    VISION_MOUSE = "vision_mouse"


@dataclass(frozen=True)
class RuntimeEnv:
    platform: PlatformKind
    system: str
    machine: str
    python: str
    strategy: ExecStrategy
    strategy_reason: str

    @property
    def is_macos(self) -> bool:
        return self.platform == PlatformKind.MACOS


def detect_platform() -> PlatformKind:
    name = sys.platform
    if name == "darwin":
        return PlatformKind.MACOS
    if name.startswith("win"):
        return PlatformKind.WINDOWS
    if name.startswith("linux"):
        return PlatformKind.LINUX
    return PlatformKind.UNKNOWN


def select_strategy(kind: PlatformKind | None = None) -> tuple[ExecStrategy, str]:
    kind = kind or detect_platform()
    if kind == PlatformKind.MACOS:
        return (
            ExecStrategy.ACCESSIBILITY_FIRST,
            "检测到 macOS：优先 Accessibility（按控件名点击），失败回退截屏视觉点击",
        )
    if kind == PlatformKind.WINDOWS:
        return (
            ExecStrategy.VISION_MOUSE,
            "检测到 Windows：暂用截屏视觉 + 键鼠（后续可接 UI Automation）",
        )
    if kind == PlatformKind.LINUX:
        return (
            ExecStrategy.VISION_MOUSE,
            "检测到 Linux：暂用截屏视觉 + 键鼠（后续可接 AT-SPI）",
        )
    return (
        ExecStrategy.VISION_MOUSE,
        "未知平台：回退截屏视觉 + 键鼠",
    )


def probe_runtime() -> RuntimeEnv:
    kind = detect_platform()
    strategy, reason = select_strategy(kind)
    return RuntimeEnv(
        platform=kind,
        system=platform.system(),
        machine=platform.machine(),
        python=platform.python_version(),
        strategy=strategy,
        strategy_reason=reason,
    )
