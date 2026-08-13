"""macOS Accessibility：通过 System Events 按控件名点击（不依赖像素坐标）。"""

from __future__ import annotations

import subprocess
import time
from typing import Optional, Tuple

from src.perception.app_info import frontmost_app_name, resolve_app_candidates


def _run_osascript(script: str, timeout: float = 12.0) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "Accessibility 查询超时"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return False, err or out or "osascript 失败"
    return True, out


def click_ui_element_by_name(
    element_name: str,
    *,
    process_name: Optional[str] = None,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """
    在指定（或前台）进程窗口中，按 name/value/description 包含目标文案的控件执行 click。

    成功返回 (True, 说明)；失败 (False, 原因) —— 调用方应回退到像素点击。
    """
    name = (element_name or "").strip()
    if not name:
        return False, "element_name 为空"

    proc = (process_name or "").strip() or frontmost_app_name()
    # WeChat 进程名可能是 WeChat
    candidates = resolve_app_candidates(proc) if proc else [proc]
    # 前台进程名优先
    ordered = []
    for c in [proc, *candidates]:
        if c and c not in ordered:
            ordered.append(c)

    if dry_run:
        return True, f"[dry-run] ax_click name={name!r} process≈{ordered[0]!r}"

    for proc_name in ordered:
        ok, detail = _click_in_process(proc_name, name)
        if ok:
            time.sleep(0.35)
            return True, f"ax_click ok process={proc_name!r} name={name!r} ({detail})"
    return False, f"ax_click 未找到控件 name={name!r} processes={ordered}"


def _click_in_process(process_name: str, element_name: str) -> Tuple[bool, str]:
    # 转义 AppleScript 字符串
    p = process_name.replace("\\", "\\\\").replace('"', '\\"')
    n = element_name.replace("\\", "\\\\").replace('"', '\\"')

    # 分几层尝试，避免 entire contents 在复杂 App 上卡死太久
    scripts = [
        # 1) 窗口内直接匹配
        f'''
tell application "System Events"
  tell process "{p}"
    if (count of windows) is 0 then return "no-window"
    set win to window 1
    try
      set el to first UI element of win whose name contains "{n}"
      click el
      return "name"
    end try
    try
      set el to first UI element of win whose value contains "{n}"
      click el
      return "value"
    end try
    try
      set el to first UI element of win whose description contains "{n}"
      click el
      return "description"
    end try
    return "miss-l1"
  end tell
end tell
''',
        # 2) 常见容器：scroll area / table / list
        f'''
tell application "System Events"
  tell process "{p}"
    if (count of windows) is 0 then return "no-window"
    set win to window 1
    repeat with area in (every scroll area of win)
      try
        set el to first UI element of area whose name contains "{n}"
        click el
        return "scroll-name"
      end try
      try
        set el to first UI element of area whose value contains "{n}"
        click el
        return "scroll-value"
      end try
    end repeat
    repeat with tbl in (every table of win)
      try
        set el to first UI element of tbl whose name contains "{n}"
        click el
        return "table-name"
      end try
    end repeat
    return "miss-l2"
  end tell
end tell
''',
        # 3) 受限 entire contents（超时由 Python 控制）
        f'''
tell application "System Events"
  tell process "{p}"
    if (count of windows) is 0 then return "no-window"
    set win to window 1
    set elems to entire contents of win
    repeat with e in elems
      try
        set nm to name of e as text
        if nm contains "{n}" then
          click e
          return "entire-name"
        end if
      end try
      try
        set vv to value of e as text
        if vv contains "{n}" then
          click e
          return "entire-value"
        end if
      end try
    end repeat
    return "miss-l3"
  end tell
end tell
''',
    ]

    last = "miss"
    for i, script in enumerate(scripts, 1):
        timeout = 6.0 if i < 3 else 10.0
        ok, out = _run_osascript(script, timeout=timeout)
        if not ok:
            last = out
            continue
        if out.startswith("miss") or out == "no-window":
            last = out
            continue
        return True, f"level{i}:{out}"
    return False, last


def accessibility_available() -> bool:
    """粗测：能否访问前台进程的窗口列表（需辅助功能权限）。"""
    script = '''
tell application "System Events"
  tell (first process whose frontmost is true)
    return (count of windows) as text
  end tell
end tell
'''
    ok, _ = _run_osascript(script, timeout=5.0)
    return ok
