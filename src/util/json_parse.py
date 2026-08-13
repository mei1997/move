"""宽松解析模型输出的 JSON。"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def parse_model_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("空响应")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0))

    last_err: Optional[Exception] = None
    for cand in candidates:
        for variant in (_as_is, _normalize_jsonish):
            try:
                data = json.loads(variant(cand))
                if isinstance(data, dict):
                    return data
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
    raise ValueError(f"无法解析 JSON: {last_err}\n原文前200字: {text[:200]!r}")


def _as_is(s: str) -> str:
    return s


def _normalize_jsonish(s: str) -> str:
    """处理单引号、True/False、尾逗号等常见模型输出问题。"""
    s = s.strip()
    # 中文弯引号
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    # 裸 true/false/null 大小写
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "null", s)
    # 尾逗号
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # 单引号 key/value → 双引号（保守：成对替换）
    if "'" in s and '"' not in s:
        s = s.replace("'", '"')
    elif "'" in s:
        # {'a': 1} 风格
        s = re.sub(r"'([^']*)'", r'"\1"', s)
    return s
