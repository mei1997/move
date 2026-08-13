from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class ActionName(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE = "move"
    SCROLL = "scroll"
    SCROLL_BOTTOM = "scroll_bottom"
    REVEAL_DOCK = "reveal_dock"
    TYPE = "type"
    HOTKEY = "hotkey"
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    WAIT = "wait"
    DONE = "done"
    FAIL = "fail"


class ClickAction(BaseModel):
    action: Literal["click", "double_click", "right_click"]
    x: int = Field(..., description="屏幕逻辑坐标 X")
    y: int = Field(..., description="屏幕逻辑坐标 Y")
    thought: str = ""
    done: bool = False


class MoveAction(BaseModel):
    action: Literal["move"]
    x: int
    y: int
    thought: str = ""
    done: bool = False


class ScrollAction(BaseModel):
    action: Literal["scroll"]
    x: int
    y: int
    clicks: int = Field(..., description="正数向上，负数向下")
    thought: str = ""
    done: bool = False


class ScrollBottomAction(BaseModel):
    """在指定区域连续向下滚动，直到接近底部。"""

    action: Literal["scroll_bottom"]
    x: int
    y: int
    thought: str = ""
    done: bool = False


class RevealDockAction(BaseModel):
    action: Literal["reveal_dock"]
    thought: str = ""
    done: bool = False


class TypeAction(BaseModel):
    action: Literal["type"]
    text: str
    thought: str = ""
    done: bool = False


class HotkeyAction(BaseModel):
    action: Literal["hotkey"]
    keys: list[str] = Field(..., description="如 ['command', 'space']")
    thought: str = ""
    done: bool = False


class OpenAppAction(BaseModel):
    action: Literal["open_app"]
    app_name: str
    thought: str = ""
    done: bool = False


class CloseAppAction(BaseModel):
    """关闭应用：不传 app_name 则关闭当前前台应用。"""

    action: Literal["close_app"]
    app_name: Optional[str] = None
    thought: str = ""
    done: bool = False


class WaitAction(BaseModel):
    action: Literal["wait"]
    seconds: float = 1.0
    thought: str = ""
    done: bool = False


class DoneAction(BaseModel):
    action: Literal["done"]
    thought: str = ""
    summary: str = ""
    done: bool = True


class FailAction(BaseModel):
    action: Literal["fail"]
    thought: str = ""
    reason: str = ""
    done: bool = True


AgentAction = Union[
    ClickAction,
    MoveAction,
    ScrollAction,
    ScrollBottomAction,
    RevealDockAction,
    TypeAction,
    HotkeyAction,
    OpenAppAction,
    CloseAppAction,
    WaitAction,
    DoneAction,
    FailAction,
]


class PlannerResponse(BaseModel):
    """模型输出的下一步动作。"""

    thought: str = Field(..., description="简短推理：看到了什么、为何这么做")
    action: ActionName
    x: Optional[int] = None
    y: Optional[int] = None
    # 目标元素在截图中的包围盒 [x1,y1,x2,y2]，点击类动作优先用其中心
    target_bbox: Optional[list[int]] = None
    target_label: Optional[str] = None
    # 本步成功后界面应呈现的状态，供动作后校验
    expected_outcome: Optional[str] = None
    clicks: Optional[int] = None
    text: Optional[str] = None
    keys: Optional[list[str]] = None
    seconds: Optional[float] = None
    app_name: Optional[str] = None
    summary: Optional[str] = None
    reason: Optional[str] = None
    done: bool = False

    def resolve_xy(
        self,
        screen_size: Optional[tuple[int, int]] = None,
    ) -> tuple[Optional[int], Optional[int]]:
        """有 target_bbox 时用中心点，否则用 x/y。"""
        from src.schema.geometry import bbox_center

        if self.target_bbox and len(self.target_bbox) == 4:
            return bbox_center(self.target_bbox, screen_size)
        return self.x, self.y

    def to_action(
        self,
        screen_size: Optional[tuple[int, int]] = None,
    ) -> AgentAction:
        name = self.action.value if isinstance(self.action, ActionName) else self.action
        base = {"thought": self.thought, "done": self.done}
        x, y = self.resolve_xy(screen_size)

        if name in ("click", "double_click", "right_click"):
            if x is None or y is None:
                raise ValueError(f"{name} 需要 target_bbox 或 x,y")
            return ClickAction(action=name, x=x, y=y, **base)  # type: ignore[arg-type]
        if name == "move":
            if x is None or y is None:
                raise ValueError("move 需要 target_bbox 或 x,y")
            return MoveAction(action="move", x=x, y=y, **base)
        if name == "scroll":
            if x is None or y is None or self.clicks is None:
                raise ValueError("scroll 需要 x,y(或 bbox) 与 clicks")
            return ScrollAction(
                action="scroll", x=x, y=y, clicks=self.clicks, **base
            )
        if name == "scroll_bottom":
            if x is None or y is None:
                raise ValueError("scroll_bottom 需要区域中心 x,y 或 bbox")
            return ScrollBottomAction(action="scroll_bottom", x=x, y=y, **base)
        if name == "reveal_dock":
            return RevealDockAction(action="reveal_dock", **base)
        if name == "type":
            if not self.text:
                raise ValueError("type 需要 text")
            return TypeAction(action="type", text=self.text, **base)
        if name == "hotkey":
            if not self.keys:
                raise ValueError("hotkey 需要 keys")
            return HotkeyAction(action="hotkey", keys=self.keys, **base)
        if name == "open_app":
            if not self.app_name:
                raise ValueError("open_app 需要 app_name")
            return OpenAppAction(action="open_app", app_name=self.app_name, **base)
        if name == "close_app":
            return CloseAppAction(action="close_app", app_name=self.app_name, **base)
        if name == "wait":
            return WaitAction(action="wait", seconds=self.seconds or 1.0, **base)
        if name == "done":
            return DoneAction(
                action="done",
                summary=self.summary or self.thought,
                thought=self.thought,
                done=True,
            )
        if name == "fail":
            return FailAction(
                action="fail",
                reason=self.reason or self.thought,
                thought=self.thought,
                done=True,
            )
        raise ValueError(f"未知动作: {name}")
