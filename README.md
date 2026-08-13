# Move — 自然语言控制电脑

用户输入一段指令，程序**先检测运行环境再选策略**：macOS 优先用 Accessibility 按控件名点击，失败再回退「截屏 → 视觉模型 → 键鼠」。

详见设计说明 [`read.md`](./read.md)。

## 环境要求

- macOS（已在当前仓库按此实现）
- Python 3.9+
- 系统权限：
  - **屏幕录制**（截屏）
  - **辅助功能**（控制鼠标键盘）  
  在「系统设置 → 隐私与安全性」中授权给「终端」或你使用的 IDE。

## 安装

```bash
cd /Users/yaoji_mei/Documents/mycode/move
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY（可用兼容代理 BASE_URL）
```

## 使用

默认**安静模式**（日志写 `logs/`，不往终端狂刷），避免 Terminal/Cursor 因输出抢焦点。

```bash
cd /Users/yaoji_mei/Documents/mycode/move
source .venv/bin/activate

# 推荐：终端.app 启动后立刻 Cmd+H 隐藏窗口
python -m src --max-steps 25 --delay 1.2 "打开微信，给文件传输助手发送：你好"

# 另开一个终端看进度
tail -f logs/agent_*.log

# 调试才开终端刷屏（容易抢焦点）
python -m src -v --dry-run "打开备忘录"
```

紧急停止：切回终端窗口按 `Ctrl+C`。

说明：截屏 / 鼠标点击本身不要求控制端在前台；抢焦点主要是因为往 Terminal 窗口打印日志。安静模式就是为了「截图 → 调模型 → 点击」时控制端尽量不抢前台。

## 架构

```
指令 → AgentLoop
         ├─ perception/screenshot  截屏（缩放到逻辑分辨率）
         ├─ perception/app_info    读取菜单栏前台应用名
         ├─ agent/planner          多模态模型输出 JSON 动作
         └─ action/mouse           click / scroll_bottom / open_app / …
```

新增能力：
- **应用技能库**：`skills/apps/*.json`，按前台 App 注入细步骤（如微信 Return 发送 / Shift+Return 换行）
- **打开即最大化**：目标应用会铺满主屏，减少点到后面 Terminal 导致焦点乱跳
- **元素中心点击**：模型给出 `target_bbox`，程序点包围盒偏上中心，减少点到下一行
- **动作后校验重试**：点击后截屏核对是否达标；未达标则按偏差修正坐标重试
- **前台应用识别**：每步注入菜单栏应用名；错应用只用 `open_app` 激活，不关原页面；动作后若焦点被 Cursor 抢走会自动拉回
- **程序坞**：仅当还要用坞打开应用且坞不可见时才 `reveal_dock`；已在目标应用内会拦截无圈 reveal_dock
- **滚到底**：`scroll_bottom` 在内容区连续下拉
- **显示程序坞**：`reveal_dock` 移到屏幕底边截图保存在 `screenshots/`，便于回放排查。

## 配置（.env）

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | API Key |
| `OPENAI_BASE_URL` | 默认 `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 需支持视觉，默认 `gpt-4o` |
| `MAX_STEPS` | 最大循环步数 |
| `ACTION_DELAY` | 每步动作后等待秒数 |
| `DRY_RUN` | `true` 时不真实点击 |
