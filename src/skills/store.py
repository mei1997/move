"""按前台应用加载 skills/apps/*.json 技能卡。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import ROOT
from src.perception.app_info import apps_match, normalize_app_name

SKILLS_DIR = ROOT / "skills" / "apps"


@lru_cache(maxsize=1)
def _load_all() -> List[Dict[str, Any]]:
    if not SKILLS_DIR.is_dir():
        return []
    cards: List[Dict[str, Any]] = []
    for path in sorted(SKILLS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"技能文件格式错误: {path}")
        data["_path"] = str(path)
        cards.append(data)
    return cards


def reload_skills() -> None:
    _load_all.cache_clear()


def find_app_skill(app_name: str) -> Optional[Dict[str, Any]]:
    """根据前台应用名匹配技能卡。"""
    if not app_name or app_name == "未知":
        return None
    for card in _load_all():
        names = [card.get("display_name", ""), card.get("id", "")]
        names.extend(card.get("aliases") or [])
        for n in names:
            if not n:
                continue
            if apps_match(app_name, str(n)):
                return card
            if normalize_app_name(app_name) == normalize_app_name(str(n)):
                return card
    return None


def format_skill_prompt(card: Dict[str, Any]) -> str:
    """格式化为注入 Planner 的文本。"""
    lines: List[str] = []
    title = card.get("display_name") or card.get("id") or "未知应用"
    lines.append(f"【应用技能库 · {title}】以下约定优先于通用猜测，必须逐步遵守：")
    layout = (card.get("layout") or "").strip()
    if layout:
        lines.append(f"界面概要：{layout}")

    for skill in card.get("skills") or []:
        sid = skill.get("id", "")
        stitle = skill.get("title", sid)
        when = skill.get("when", "")
        lines.append(f"\n技能 `{sid}` — {stitle}")
        if when:
            lines.append(f"  适用：{when}")
        steps = skill.get("steps") or []
        if steps:
            lines.append("  细步骤：")
            for i, s in enumerate(steps, 1):
                lines.append(f"    {i}. {s}")
        rules = skill.get("rules") or []
        if rules:
            lines.append("  硬规则：")
            for r in rules:
                lines.append(f"    - {r}")

    checklist = (card.get("checklist_before_done") or "").strip()
    if checklist:
        lines.append(f"\n完成前自检：\n{checklist}")

    lines.append(
        "\n特别提醒：若截图显示输入框已有待发文字，但会话气泡区没有该内容，"
        "禁止 action=done；下一步必须对输入框执行 hotkey keys=[\"return\"] 发送"
        "（Shift+Return 是换行，不会发送）。"
    )
    return "\n".join(lines)


def skill_prompt_for_app(app_name: str) -> str:
    card = find_app_skill(app_name)
    if not card:
        return ""
    return format_skill_prompt(card)
