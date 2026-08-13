from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Tuple

from PIL import Image

from src.config import SCREENSHOT_DIR, ensure_dirs
from src.perception.display import main_display_logical_size


@dataclass
class Screenshot:
    """截图结果：逻辑坐标尺寸 + 文件路径。"""

    path: Path
    logical_width: int
    logical_height: int
    pixel_width: int
    pixel_height: int
    scale: float

    @property
    def size(self) -> Tuple[int, int]:
        return self.logical_width, self.logical_height


def capture(monitor: int = 1, save: bool = True) -> Screenshot:
    """
    使用系统 screencapture 截主屏。

    Retina 下 PNG 为物理像素，会缩放到逻辑尺寸，便于模型输出可直接点击的坐标。
    """
    ensure_dirs()
    logical_w, logical_h = main_display_logical_size()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    raw_path = SCREENSHOT_DIR / f"_raw_{ts}.png"
    # -x 静音；-m 主屏
    subprocess.run(
        ["screencapture", "-x", "-m", str(raw_path)],
        check=True,
    )
    img = Image.open(raw_path).convert("RGB")
    pixel_w, pixel_h = img.size
    scale = pixel_w / logical_w if logical_w else 1.0

    if abs(scale - 1.0) > 0.01:
        resample = getattr(Image, "Resampling", Image).LANCZOS
        img_for_model = img.resize((logical_w, logical_h), resample)
    else:
        img_for_model = img

    path = SCREENSHOT_DIR / f"shot_{ts}.png" if save else SCREENSHOT_DIR / "_latest.png"
    img_for_model.save(path)
    try:
        raw_path.unlink(missing_ok=True)  # type: ignore[call-arg]
    except TypeError:
        if raw_path.exists():
            raw_path.unlink()

    return Screenshot(
        path=path,
        logical_width=logical_w,
        logical_height=logical_h,
        pixel_width=pixel_w,
        pixel_height=pixel_h,
        scale=scale,
    )
