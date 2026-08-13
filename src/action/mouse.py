from __future__ import annotations

import subprocess
import time
from typing import Optional, Sequence, Tuple

from src.perception.app_info import (
    close_front_window,
    frontmost_app_name,
    open_app,
    quit_app,
)
from src.perception.display import main_display_logical_size
from src.schema.actions import AgentAction

try:
    from src.action import quartz_mouse as qm
except Exception:  # pragma: no cover
    qm = None  # type: ignore


class MouseController:
    def __init__(
        self,
        dry_run: bool = False,
        action_delay: float = 0.8,
        screen_size: Optional[Tuple[int, int]] = None,
    ) -> None:
        self.dry_run = dry_run
        self.action_delay = action_delay
        self.screen_size = screen_size or main_display_logical_size()
        if qm is None and not dry_run:
            raise RuntimeError("无法加载 macOS Quartz 鼠标控制模块")

    def execute(self, action: AgentAction) -> str:
        name = action.action
        if name in ("click", "double_click", "right_click"):
            return self._click(name, action.x, action.y)  # type: ignore[attr-defined]
        if name == "move":
            return self._move(action.x, action.y)  # type: ignore[attr-defined]
        if name == "scroll":
            return self._scroll(action.x, action.y, action.clicks)  # type: ignore[attr-defined]
        if name == "scroll_bottom":
            return self._scroll_bottom(action.x, action.y)  # type: ignore[attr-defined]
        if name == "reveal_dock":
            return self._reveal_dock()
        if name == "type":
            return self._type(action.text)  # type: ignore[attr-defined]
        if name == "hotkey":
            return self._hotkey(action.keys)  # type: ignore[attr-defined]
        if name == "open_app":
            return self._open_app(action.app_name)  # type: ignore[attr-defined]
        if name == "close_app":
            return self._close_app(getattr(action, "app_name", None))
        if name == "wait":
            return self._wait(action.seconds)  # type: ignore[attr-defined]
        if name == "done":
            return f"完成: {getattr(action, 'summary', '')}"
        if name == "fail":
            return f"失败: {getattr(action, 'reason', '')}"
        return f"未执行未知动作: {name}"

    def _after(self) -> None:
        if self.action_delay > 0:
            time.sleep(self.action_delay)

    def _click(self, kind: str, x: int, y: int) -> str:
        msg = f"{kind} @ ({x}, {y})"
        if self.dry_run:
            return f"[dry-run] {msg}"
        assert qm is not None
        if kind == "click":
            qm.click(x, y)
        elif kind == "double_click":
            qm.double_click(x, y)
        else:
            qm.right_click(x, y)
        self._after()
        return msg

    def _move(self, x: int, y: int) -> str:
        msg = f"move @ ({x}, {y})"
        if self.dry_run:
            return f"[dry-run] {msg}"
        assert qm is not None
        qm.move_to(x, y)
        self._after()
        return msg

    def _scroll(self, x: int, y: int, clicks: int) -> str:
        msg = f"scroll {clicks} @ ({x}, {y})"
        if self.dry_run:
            return f"[dry-run] {msg}"
        assert qm is not None
        qm.move_to(x, y)
        qm.scroll(clicks)
        self._after()
        return msg

    def _scroll_bottom(self, x: int, y: int) -> str:
        """在内容区域连续向下滚，模拟拉到列表/聊天底部。"""
        msg = f"scroll_bottom @ ({x}, {y})"
        if self.dry_run:
            return f"[dry-run] {msg}"
        assert qm is not None
        qm.move_to(x, y)
        # macOS：负数向下；多段滚动更稳
        for _ in range(8):
            qm.scroll(-12)
            time.sleep(0.08)
        self._after()
        return msg

    def _reveal_dock(self) -> str:
        w, h = self.screen_size
        x, y = w // 2, h - 2
        msg = f"reveal_dock move→({x}, {y})"
        if self.dry_run:
            return f"[dry-run] {msg}"
        assert qm is not None
        qm.move_to(x, y)
        time.sleep(0.6)
        self._after()
        return msg

    def _type(self, text: str) -> str:
        msg = f"type {text!r}"
        if self.dry_run:
            return f"[dry-run] {msg}"
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        self._hotkey(["command", "v"])
        return msg

    def _hotkey(self, keys: Sequence[str]) -> str:
        normalized = [
            k.lower().replace("cmd", "command").replace("ctrl", "control").replace("opt", "option")
            for k in keys
        ]
        msg = f"hotkey {'+'.join(normalized)}"
        if self.dry_run:
            return f"[dry-run] {msg}"
        assert qm is not None
        qm.hotkey(normalized)
        self._after()
        return msg

    def _open_app(self, app_name: str) -> str:
        msg = f"open_app {app_name!r} (maximize)"
        if self.dry_run:
            return f"[dry-run] {msg}"
        open_app(app_name, maximize=True)
        time.sleep(0.8)
        self._after()
        return msg

    def _close_app(self, app_name: Optional[str]) -> str:
        target = (app_name or "").strip() or frontmost_app_name()
        msg = f"close_app {target!r}"
        if self.dry_run:
            return f"[dry-run] {msg}"
        # 先关窗口，再 quit，避免误关系统关键应用时卡住
        if not app_name:
            close_front_window()
            time.sleep(0.3)
        quit_app(target)
        time.sleep(0.8)
        self._after()
        return msg

    def _wait(self, seconds: float) -> str:
        msg = f"wait {seconds}s"
        if self.dry_run:
            return f"[dry-run] {msg}"
        time.sleep(seconds)
        return msg
