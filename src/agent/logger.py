from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO

from src.config import LOG_DIR, ensure_dirs


class RunLogger:
    """默认写文件；quiet 时不往 TTY 打字，避免 Terminal/Cursor 抢焦点。"""

    def __init__(self, quiet: bool = True, log_path: Optional[Path] = None) -> None:
        ensure_dirs()
        if log_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = LOG_DIR / f"agent_{ts}.log"
        self.quiet = quiet
        self.log_path = log_path
        self._fp: TextIO[str] = open(log_path, "a", encoding="utf-8")

    def log(self, message: str) -> None:
        line = message.rstrip()
        self._fp.write(line + "\n")
        self._fp.flush()
        if not self.quiet:
            print(line, flush=True)

    def close(self) -> None:
        try:
            self._fp.close()
        except Exception:
            pass
