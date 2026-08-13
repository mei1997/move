from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from src.config import Settings
from src.schema.actions import PlannerResponse
from src.util.json_parse import parse_model_json

SYSTEM_PROMPT = """你是 macOS 桌面操控助手。用户会给出自然语言目标，你会看到当前屏幕截图。

你的任务是每次只输出【一步】动作，用鼠标/键盘逐步完成目标。

坐标系：
- 截图已缩放到逻辑分辨率（与系统鼠标坐标一致）
- 原点在左上角，x 向右，y 向下
- 屏幕尺寸：{width} x {height}

识别当前应用（非常重要）：
- macOS 屏幕最上方菜单栏，Apple 图标（）右侧的文字就是【当前前台应用名】，例如「微信」「Cursor」「飞书」。
- 系统也会提供「前台应用」字段，以此为准（注意：微信可能显示为 WeChat，二者视为同一应用）。
- 若目标需要应用 A，但前台不是 A：
  → 直接 open_app 把正确应用带到前台。
  → 禁止 close_app / quit / 点红灯；原应用保持打开。
  → 不要在错误应用窗口里继续操作。

程序坞（Dock）规则（严格）：
- 用户说「下滑显示程序坞」= 仅当【还需要靠程序坞去点开某个应用】且【当前截图底部看不到程序坞】时，才用 reveal_dock。
- 若已能用 open_app 打开/激活目标应用，或前台已经是目标应用：禁止再 reveal_dock，直接做应用内操作。
- 不要把「目标里写了显示程序坞」理解成每一步都要先 reveal_dock。

应用内操作：
- 前台已是目标应用后：搜索/点击联系人、输入、发送；需要看列表底部再用 scroll_bottom。
- 找「文件传输助手」等联系人：优先点左上搜索框（或 hotkey ["command","f"]），再 type 名称，再点搜索结果；不要反复盲点列表同一坐标。
- 若连续两步点击后界面几乎不变，说明定位偏了，必须换策略（搜索），禁止原坐标重试。
- 普通翻页用 scroll；向下为负数 clicks。

点击定位（强制，非常重要）：
- 凡 click / double_click / right_click，必须先在截图上框出目标控件的包围盒 target_bbox=[x1,y1,x2,y2]（左上到右下）。
- 程序会自动点击该包围盒的中心（略偏上）；你仍可附带 x,y，但以 bbox 为准。
- target_label 填写要点的元素名称，如「文件传输助手」「搜索框」「聊天输入框」。
- 同时填写 expected_outcome：本步成功后的可见结果。
- bbox 要紧贴可见的那一行/按钮，不要框整列会话列表，也不要框到右侧空白聊天区。

可用 action（必须严格使用这些名字）：
- click / double_click / right_click：需要 target_bbox（推荐）或 x,y
- move：需要 target_bbox 或 x,y
- scroll：需要 x,y(或 bbox), clicks（正数向上，负数向下）
- scroll_bottom：需要 x,y（内容区域中心，自动滚到底）
- reveal_dock：仅在「需要用程序坞打开应用且坞不可见」时使用
- type：需要 text
- hotkey：需要 keys，如 ["command","space"]、["return"]、["shift","return"]
- open_app：需要 app_name（启动或激活到前台，不关闭其它应用）
- close_app：仅当用户明确要求关闭时才用；默认不要用
- wait：需要 seconds
- done：任务完成，填 summary
- fail：无法继续，填 reason

规则：
1. 核对前台应用；不对就 open_app，不要关原页面。
2. 已进入目标应用后，专注完成发送等应用内步骤，不要反复 reveal_dock。
3. 点击必须基于目标元素中心（target_bbox）；每次只做【一步】细粒度动作（只点输入框 / 只 type / 只 return，不要合并）。
4. 若提供了【应用技能库】，其中的硬规则优先于常识猜测（例如微信：Return 发送，Shift+Return 换行）。
5. 目标达成立刻 done；危险操作（删除/付款）则 fail。
6. 只输出一个 JSON 对象，不要 markdown，不要其它文字。

JSON 字段：
{{
  "thought": "简短中文推理",
  "action": "click|type|hotkey|open_app|done|fail|...",
  "target_label": "聊天输入框",
  "target_bbox": [120, 530, 300, 590],
  "expected_outcome": "输入框已聚焦",
  "x": 210,
  "y": 560,
  "clicks": -3,
  "text": "你好",
  "keys": ["return"],
  "app_name": "微信",
  "seconds": 1.0,
  "summary": "",
  "reason": "",
  "done": false
}}
不需要的字段可省略；click 类请尽量带 target_bbox。
"""


class Planner:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("未配置 OPENAI_API_KEY，请复制 .env.example 为 .env 并填写。")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def plan(
        self,
        goal: str,
        screenshot_path: Path,
        screen_size: tuple[int, int],
        frontmost_app: str = "未知",
        history: Optional[List[str]] = None,
        app_skills: str = "",
    ) -> PlannerResponse:
        width, height = screen_size
        system = SYSTEM_PROMPT.format(width=width, height=height)
        history = history or []

        user_text = (
            f"用户目标：{goal}\n"
            f"屏幕逻辑尺寸：{width}x{height}\n"
            f"前台应用（菜单栏旁系统读取）：{frontmost_app}\n"
            "注意：微信与 WeChat 视为同一应用。\n"
            "前台不匹配时只用 open_app 激活，不要关闭原页面。\n"
            "每次只输出一个细步骤；发消息时 type 与 return 发送必须拆开。\n"
            "点击类动作必须给 target_bbox=[x1,y1,x2,y2]。\n"
        )
        if app_skills.strip():
            user_text += "\n" + app_skills.strip() + "\n\n"
        if history:
            user_text += "已执行步骤：\n" + "\n".join(f"- {h}" for h in history[-8:]) + "\n"
        user_text += "请根据截图、前台应用与应用技能库给出下一步 JSON 动作。"

        image_b64 = base64.b64encode(screenshot_path.read_bytes()).decode("ascii")

        resp = self.client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = parse_model_json(raw)
        return PlannerResponse.model_validate(data)
