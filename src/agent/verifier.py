"""动作后校验：对比截图是否达到上一步预期，并给出坐标修正。"""

from __future__ import annotations

import base64
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field

from src.config import Settings
from src.util.json_parse import parse_model_json

VERIFY_PROMPT = """你是 UI 操作校验器。根据【动作后】的截图，判断上一步是否达到预期。

只输出一个 JSON 对象（必须使用双引号，不要单引号，不要 markdown）：
{
  "success": false,
  "observed": "现在实际看到什么（中文短句）",
  "expected": "期望是什么",
  "delta_x": 0,
  "delta_y": 0,
  "hint": "下一步建议（中文短句）"
}

规则：
- success=true 仅当截图明确显示已达到 expected_outcome。
- 若点错相邻列表项（例如目标是「文件传输助手」却选中了下方「微信支付」），success=false，
  delta_y 给负数（例如 -40 到 -70，表示下次点击应上移），delta_x 通常为 0。
- 若点到右侧空白区，delta_x 给负数。
- 若尚未进入聊天、右侧标题不是目标联系人，success=false。
- 不要输出 markdown。
"""


class VerifyResult(BaseModel):
    success: bool = False
    observed: str = ""
    expected: str = ""
    delta_x: int = 0
    delta_y: int = 0
    hint: str = ""


class ActionVerifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def verify(
        self,
        *,
        screenshot_path: Path,
        last_action: str,
        expected_outcome: str,
        target_label: str = "",
    ) -> VerifyResult:
        user = (
            f"上一步动作：{last_action}\n"
            f"目标元素：{target_label or '未知'}\n"
            f"期望结果：{expected_outcome}\n"
            "请根据截图判断是否达成，并给出坐标修正 delta_x/delta_y（像素，相对上次点击）。"
        )
        image_b64 = base64.b64encode(screenshot_path.read_bytes()).decode("ascii")
        resp = self.client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            messages=[
                {"role": "system", "content": VERIFY_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user},
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
        return VerifyResult.model_validate(data)
