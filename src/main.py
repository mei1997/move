from __future__ import annotations

import sys

import click

from src.agent.loop import AgentLoop
from src.config import get_settings


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("goal", required=False)
@click.option("--dry-run", is_flag=True, help="只规划不真实点击")
@click.option("--max-steps", type=int, default=None, help="最大步数")
@click.option("--delay", type=float, default=None, help="每步动作后等待秒数")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="同时在终端刷日志（容易抢焦点，调试用）",
)
def main(
    goal: str | None,
    dry_run: bool,
    max_steps: int | None,
    delay: float | None,
    verbose: bool,
) -> None:
    """根据自然语言指令，截屏并用鼠标模拟操作电脑。

    默认安静模式：日志写入 logs/，减少 Terminal 抢焦点。
    建议启动后立刻 Cmd+H 隐藏终端，另开窗口用 tail -f 看日志。

    示例：

      python -m src "打开微信给文件传输助手发你好"

      python -m src -v --dry-run "打开备忘录"
    """
    if not goal:
        goal = click.prompt("请输入要完成的指令")

    settings = get_settings()
    if dry_run:
        settings.dry_run = True
    if max_steps is not None:
        settings.max_steps = max_steps
    if delay is not None:
        settings.action_delay = delay
    settings.quiet = not verbose

    try:
        result = AgentLoop(settings).run(goal)
    except KeyboardInterrupt:
        print("\n已中断", flush=True)
        sys.exit(130)
    except Exception as exc:
        print(f"错误：{exc}", flush=True)
        sys.exit(1)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
