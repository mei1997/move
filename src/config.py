from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_DIR = ROOT / "screenshots"
LOG_DIR = ROOT / "logs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    max_steps: int = 20
    action_delay: float = 0.8
    dry_run: bool = False
    # 默认安静：日志写文件，减少 Terminal 因刷屏抢焦点
    quiet: bool = True
    # 点击后校验失败时的最大重试次数
    verify_retries: int = 3


def get_settings() -> Settings:
    return Settings()


def ensure_dirs() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
