from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Set

from src.action.mouse import MouseController
from src.agent.logger import RunLogger
from src.agent.planner import Planner
from src.agent.verifier import ActionVerifier
from src.config import Settings, ensure_dirs
from src.perception.app_info import (
    apps_match,
    ensure_frontmost,
    frontmost_app_name,
    infer_target_app_from_goal,
    maximize_front_window,
    normalize_app_name,
    open_app,
)
from src.perception.screenshot import capture
from src.runtime.platform import ExecStrategy, RuntimeEnv, probe_runtime
from src.schema.actions import AgentAction, ClickAction
from src.skills.store import find_app_skill, skill_prompt_for_app

# 跑 Agent 的宿主：往这些窗口刷日志会把焦点抢走
CONTROLLER_APPS: Set[str] = {
    "terminal",
    "iterm2",
    "iterm",
    "cursor",
    "code",
    "warp",
    "alacritty",
    "kitty",
}


def _is_controller_app(name: str) -> bool:
    n = normalize_app_name(name)
    return any(n == c or c in n for c in CONTROLLER_APPS)


@dataclass
class StepRecord:
    step: int
    thought: str
    action: AgentAction
    result: str
    screenshot: str
    frontmost_app: str = ""


@dataclass
class RunResult:
    success: bool
    message: str
    steps: List[StepRecord] = field(default_factory=list)
    log_path: str = ""


class AgentLoop:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        ensure_dirs()
        self.env: RuntimeEnv = probe_runtime()
        self.planner = Planner(self.settings)
        self.verifier = ActionVerifier(self.settings)
        self.controller = MouseController(
            dry_run=self.settings.dry_run,
            action_delay=self.settings.action_delay,
        )
        self.logger = RunLogger(quiet=self.settings.quiet)
        self._ax = None
        if self.env.strategy == ExecStrategy.ACCESSIBILITY_FIRST:
            from src.action import accessibility_mac as ax

            self._ax = ax

    def _log(self, msg: str) -> None:
        self.logger.log(msg)

    def _keep_pinned(self, pinned_app: Optional[str], *, why: str) -> None:
        """若焦点落在宿主终端/IDE，静默拉回目标应用（不 print 到 TTY）。"""
        if not pinned_app or self.settings.dry_run:
            return
        now = frontmost_app_name()
        if apps_match(now, pinned_app):
            return
        self._log(f"[focus] {why}: 前台={now} → 激活 {pinned_app}")
        # 焦点恢复时只激活，不反复最大化（避免窗口抖动）
        ensure_frontmost(pinned_app, maximize=False)
        time.sleep(0.2)

    def run(self, goal: str) -> RunResult:
        history: List[str] = []
        records: List[StepRecord] = []
        pinned_app = infer_target_app_from_goal(goal)
        maximized_once = False

        self._log(f"目标: {goal}")
        self._log(f"日志文件: {self.logger.log_path}")
        self._log(
            f"环境: platform={self.env.platform.value} "
            f"system={self.env.system}/{self.env.machine} python={self.env.python}"
        )
        self._log(f"策略: {self.env.strategy.value} — {self.env.strategy_reason}")
        if self._ax is not None:
            ax_ok = self._ax.accessibility_available()
            self._log(f"Accessibility 可用: {ax_ok}")
            if not ax_ok:
                self._log("提示: 请在「系统设置 → 隐私与安全性 → 辅助功能」中授权运行本程序的终端")
        if pinned_app:
            self._log(f"推断目标应用: {pinned_app}")
        if self.settings.quiet:
            print(
                f"安静模式运行中（避免抢焦点）。日志: {self.logger.log_path}\n"
                f"策略: {self.env.strategy.value}\n"
                f"可用: tail -f {self.logger.log_path}\n"
                "建议立即 Cmd+H 隐藏终端，等待完成。",
                flush=True,
            )
        if self.settings.dry_run:
            self._log("DRY_RUN=true")

        # 一开始就打开并最大化目标应用，盖住 Terminal，减少误点
        if pinned_app and not self.settings.dry_run:
            self._log(f"启动并最大化: {pinned_app}")
            open_app(pinned_app, maximize=True)
            maximized_once = True
            time.sleep(0.6)

        try:
            return self._run_loop(goal, pinned_app, history, records, maximized_once)
        finally:
            self.logger.close()

    def _run_loop(
        self,
        goal: str,
        pinned_app: Optional[str],
        history: List[str],
        records: List[StepRecord],
        maximized_once: bool,
    ) -> RunResult:
        for step in range(1, self.settings.max_steps + 1):
            self._keep_pinned(pinned_app, why="截屏前")

            shot = capture()
            app_name = frontmost_app_name()
            skill_card = find_app_skill(app_name)
            app_skills = skill_prompt_for_app(app_name)
            self._log(
                f"\n步骤 {step}/{self.settings.max_steps}  "
                f"截图 {shot.path.name} ({shot.logical_width}x{shot.logical_height})  "
                f"前台={app_name}"
            )
            if skill_card:
                self._log(
                    f"应用技能: {skill_card.get('display_name') or skill_card.get('id')} "
                    f"({skill_card.get('_path')})"
                )

            planned = self.planner.plan(
                goal=goal,
                screenshot_path=shot.path,
                screen_size=shot.size,
                frontmost_app=app_name,
                history=history,
                app_skills=app_skills,
            )
            action = planned.to_action(screen_size=shot.size)

            if (
                action.action == "reveal_dock"
                and pinned_app
                and apps_match(app_name, pinned_app)
            ):
                self._log("已在目标应用内，拦截 reveal_dock，重新规划")
                history.append(
                    f"#{step} 系统拦截: 前台已是 {app_name}，禁止 reveal_dock，请点击联系人或输入发送"
                )
                continue

            self._log(f"思考: {planned.thought}")
            if planned.target_bbox:
                cx, cy = planned.resolve_xy(shot.size)
                self._log(
                    f"目标: {planned.target_label or '?'}  "
                    f"bbox={planned.target_bbox} → 中心=({cx}, {cy})"
                )
            self._log(f"动作: {action.model_dump()}")

            self._keep_pinned(pinned_app, why="动作前")
            result_msg = self._execute_with_strategy(
                action=action,
                planned_label=planned.target_label or "",
                process_name=app_name,
            )
            self._log(f"执行: {result_msg}")

            # 点击类：动作后校验；未达标则按 delta 修正坐标重试
            if (
                action.action in ("click", "double_click", "right_click")
                and not self.settings.dry_run
            ):
                expected = (
                    planned.expected_outcome
                    or f"成功选中/打开「{planned.target_label or '目标元素'}」"
                )
                result_msg = self._verify_and_retry_click(
                    action=action,
                    expected_outcome=expected,
                    target_label=planned.target_label or "",
                    pinned_app=pinned_app,
                )

            if action.action == "open_app":
                pinned_app = getattr(action, "app_name", None) or pinned_app
                if not self.settings.dry_run and pinned_app:
                    time.sleep(0.35)
                    if maximize_front_window():
                        self._log(f"已最大化窗口: {pinned_app}")
                        maximized_once = True

            if action.action not in ("done", "fail", "close_app"):
                time.sleep(0.4)
                self._keep_pinned(pinned_app, why="动作后")
                # 若从未最大化成功过，补一次
                if pinned_app and not maximized_once and not self.settings.dry_run:
                    if apps_match(frontmost_app_name(), pinned_app):
                        if maximize_front_window():
                            self._log(f"补最大化窗口: {pinned_app}")
                            maximized_once = True

            record = StepRecord(
                step=step,
                thought=planned.thought,
                action=action,
                result=result_msg,
                screenshot=str(shot.path),
                frontmost_app=app_name,
            )
            records.append(record)
            history.append(
                f"#{step} 前台={app_name} {action.action}: {result_msg} | {planned.thought}"
            )

            if action.action == "done":
                summary = getattr(action, "summary", "") or planned.thought
                self._log(f"完成: {summary}")
                print(f"完成: {summary}\n日志: {self.logger.log_path}", flush=True)
                return RunResult(
                    success=True,
                    message=summary,
                    steps=records,
                    log_path=str(self.logger.log_path),
                )

            if action.action == "fail":
                reason = getattr(action, "reason", "") or planned.thought
                self._log(f"失败: {reason}")
                print(f"失败: {reason}\n日志: {self.logger.log_path}", flush=True)
                return RunResult(
                    success=False,
                    message=reason,
                    steps=records,
                    log_path=str(self.logger.log_path),
                )

        msg = f"达到最大步数 {self.settings.max_steps}，任务未完成"
        self._log(msg)
        print(f"{msg}\n日志: {self.logger.log_path}", flush=True)
        return RunResult(
            success=False,
            message=msg,
            steps=records,
            log_path=str(self.logger.log_path),
        )

    def _verify_and_retry_click(
        self,
        *,
        action: AgentAction,
        expected_outcome: str,
        target_label: str,
        pinned_app: Optional[str],
    ) -> str:
        """点击后截屏校验；失败则按模型给出的 delta 修正重试。"""
        last_msg = f"{action.action} @ ({action.x}, {action.y})"  # type: ignore[attr-defined]
        x = int(action.x)  # type: ignore[attr-defined]
        y = int(action.y)  # type: ignore[attr-defined]
        kind = str(action.action)

        for attempt in range(1, self.settings.verify_retries + 1):
            time.sleep(0.45)
            self._keep_pinned(pinned_app, why="校验前")
            after = capture()
            try:
                verdict = self.verifier.verify(
                    screenshot_path=after.path,
                    last_action=last_msg,
                    expected_outcome=expected_outcome,
                    target_label=target_label,
                )
            except Exception as exc:  # noqa: BLE001
                self._log(f"[校验{attempt}/{self.settings.verify_retries}] 解析失败: {exc}")
                # 解析失败时默认上移重试，避免整任务中断
                from src.agent.verifier import VerifyResult

                verdict = VerifyResult(
                    success=False,
                    observed=f"校验JSON解析失败: {exc}",
                    expected=expected_outcome,
                    delta_x=0,
                    delta_y=-25,
                    hint="重新点击目标区域偏上位置",
                )
            self._log(
                f"[校验{attempt}/{self.settings.verify_retries}] "
                f"success={verdict.success} 看到={verdict.observed} "
                f"期望={verdict.expected or expected_outcome} "
                f"delta=({verdict.delta_x},{verdict.delta_y}) hint={verdict.hint}"
            )
            if verdict.success:
                return f"{last_msg} | 校验通过: {verdict.observed}"

            # 无默认上移：点到下方邻居时常见
            dx = verdict.delta_x
            dy = verdict.delta_y if verdict.delta_y != 0 else -45
            if attempt >= self.settings.verify_retries:
                break
            x = max(0, x + dx)
            y = max(0, y + dy)
            retry = ClickAction(action=kind, x=x, y=y, thought="校验失败后修正重试")  # type: ignore[arg-type]
            self._log(f"[重试] 修正点击 → ({x}, {y})")
            self._keep_pinned(pinned_app, why="重试前")
            last_msg = self.controller.execute(retry)

        return f"{last_msg} | 校验未通过: {verdict.observed}；建议={verdict.hint}"

    def _execute_with_strategy(
        self,
        *,
        action: AgentAction,
        planned_label: str,
        process_name: str,
    ) -> str:
        """
        macOS accessibility_first：点击类且有 target_label 时先按控件名 AX 点击；
        失败再回退像素坐标点击。
        """
        use_ax = (
            self.env.strategy == ExecStrategy.ACCESSIBILITY_FIRST
            and self._ax is not None
            and action.action in ("click", "double_click")
            and bool(planned_label.strip())
        )
        if use_ax:
            ok, detail = self._ax.click_ui_element_by_name(
                planned_label,
                process_name=process_name,
                dry_run=self.settings.dry_run,
            )
            if ok:
                self._log(f"[AX] {detail}")
                return detail
            self._log(f"[AX] 失败，回退像素点击: {detail}")

        return self.controller.execute(action)
