"""读取 / 激活 macOS 前台应用（菜单栏 Apple 图标旁的应用名）。"""

from __future__ import annotations

import re
import subprocess
import time
from typing import Dict, List, Optional, Set, Tuple

from src.perception.display import main_display_logical_size

# 同一应用的多种显示名
APP_ALIASES: Dict[str, Set[str]] = {
    "wechat": {"微信", "wechat", "weixin"},
    "feishu": {"飞书", "lark", "feishu", "larksuite"},
    "qq": {"qq", "腾讯qq", "qqformac"},
    "tonghuashun": {"同花顺", "同花顺远航版", "hexin", "ifind"},
    "cursor": {"cursor"},
    "safari": {"safari"},
    "notes": {"notes", "备忘录"},
}


def normalize_app_name(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").strip().lower())


def apps_match(a: str, b: str) -> bool:
    """判断两个应用名是否指向同一应用（微信 ≈ WeChat）。"""
    na, nb = normalize_app_name(a), normalize_app_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    for group in APP_ALIASES.values():
        if na in group and nb in group:
            return True
    return False


def infer_target_app_from_goal(goal: str) -> Optional[str]:
    """从用户目标里粗提取要操作的应用名。"""
    text = goal or ""
    patterns = [
        (r"微信|WeChat|wechat", "微信"),
        (r"飞书|Lark|Feishu", "飞书"),
        (r"(?<![A-Za-z])QQ(?![A-Za-z])|腾讯QQ", "QQ"),
        (r"同花顺", "同花顺"),
        (r"Safari|safari", "Safari"),
        (r"备忘录|Notes", "备忘录"),
        (r"系统设置|System Settings", "系统设置"),
    ]
    for pat, name in patterns:
        if re.search(pat, text, re.I):
            return name
    return None


def frontmost_app_name() -> str:
    """返回当前前台应用显示名，例如「微信」「Cursor」「飞书」。"""
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    try:
        out = subprocess.check_output(["osascript", "-e", script], text=True).strip()
        return out or "未知"
    except subprocess.CalledProcessError:
        return "未知"


def quit_app(name: str) -> None:
    """退出指定应用（按进程/应用名）。"""
    script = f'tell application "{name}" to quit'
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def close_front_window() -> None:
    """关闭前台应用当前窗口（Command+W）。"""
    script = 'tell application "System Events" to keystroke "w" using command down'
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def resolve_app_candidates(name: str) -> List[str]:
    aliases = {
        "微信": ["WeChat", "微信"],
        "wechat": ["WeChat", "微信"],
        "飞书": ["飞书", "Lark", "Feishu"],
        "lark": ["飞书", "Lark"],
        "feishu": ["飞书", "Lark", "Feishu"],
        "qq": ["QQ", "QQ for Mac", "腾讯QQ"],
        "腾讯qq": ["QQ", "QQ for Mac"],
        "同花顺": ["同花顺", "同花顺远航版", "iFinD"],
        "tonghuashun": ["同花顺", "同花顺远航版"],
        "safari": ["Safari"],
        "备忘录": ["Notes", "备忘录"],
        "系统设置": ["System Settings", "系统设置"],
    }
    key = name.strip().lower()
    return aliases.get(key) or aliases.get(name.strip()) or [name]


def maximize_front_window(
    size: Optional[Tuple[int, int]] = None,
) -> bool:
    """
    将前台应用主窗口铺满主屏（最大化，非全屏 Space）。
    避免后面露出 Terminal 等窗口被误点。
    """
    w, h = size or main_display_logical_size()
    script = f'''
tell application "System Events"
  tell (first process whose frontmost is true)
    if (count of windows) is 0 then return false
    set win to window 1
    try
      set value of attribute "AXFullScreen" of win to false
    end try
    set position of win to {{0, 0}}
    set size of win to {{{int(w)}, {int(h)}}}
  end tell
end tell
'''
    proc = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def open_app(name: str, *, maximize: bool = True) -> None:
    """启动或激活应用到前台，不关闭其它已打开的应用；可选最大化窗口。"""
    candidates = resolve_app_candidates(name)
    last_err: Optional[Exception] = None
    for cand in candidates:
        try:
            subprocess.run(["open", "-a", cand], check=True, capture_output=True)
            subprocess.run(
                ["osascript", "-e", f'tell application "{cand}" to activate'],
                check=False,
                capture_output=True,
            )
            if maximize:
                time.sleep(0.45)
                maximize_front_window()
            return
        except subprocess.CalledProcessError as exc:
            last_err = exc
            continue
    if last_err:
        raise RuntimeError(f"无法打开应用: {name}") from last_err


def ensure_frontmost(name: str, *, maximize: bool = False) -> bool:
    """若前台不是目标应用，则激活它。返回是否已是/已切到目标。"""
    current = frontmost_app_name()
    if apps_match(current, name):
        if maximize:
            maximize_front_window()
        return True
    open_app(name, maximize=maximize)
    return apps_match(frontmost_app_name(), name)
