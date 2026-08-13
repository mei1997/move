"""动作坐标：优先用目标元素包围盒中心。"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple


def bbox_center(
    bbox: Sequence[int],
    screen_size: Optional[Tuple[int, int]] = None,
    *,
    y_bias: float = 0.28,
) -> Tuple[int, int]:
    """
    bbox: [x1, y1, x2, y2] 左上-右下。
    y_bias: 取竖直方向的相对位置，默认 0.28（偏上），避免点到下方相邻行。
    """
    if len(bbox) != 4:
        raise ValueError(f"bbox 需要 4 个数，收到: {bbox}")
    x1, y1, x2, y2 = (int(v) for v in bbox)
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    cx = (x1 + x2) // 2
    bias = min(max(y_bias, 0.15), 0.85)
    cy = y1 + int((y2 - y1) * bias)
    if screen_size:
        w, h = screen_size
        cx = max(0, min(w - 1, cx))
        cy = max(0, min(h - 1, cy))
    return cx, cy
