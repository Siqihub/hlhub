# AutoDy 抖音每日续火花

Windows 本地自动化工具：每天 07:30 从文案库随机选择一条本轮未使用的文案，并发送给配置的抖音好友。首次扫码登录后复用本地浏览器登录状态；同一天重复运行只补发失败目标。

> 仅用于个人低频、自用场景。抖音页面和登录策略可能变化，使用者需遵守平台规则并自行承担账号风险。本工具不会绕过验证码或安全验证。

## 环境要求

- Windows 10/11
- Python 3.11 或更高版本
- 可正常访问 `https://www.douyin.com/chat`

## 安装

在项目目录打开 PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
playwright install chromium
Copy-Item config.example.yaml config.yaml
Copy-Item messages.example.txt messages.txt
```

如果 PowerShell 阻止激活脚本，可在当前窗口执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## 配置

编辑 `config.yaml`：

```yaml
targets:
  - name: "好友备注名"
  - name: "另一位好友备注名"
messages_file: messages.txt
profile_dir: data/browser-profile
state_file: data/state.json
lock_file: data/autody.lock
artifact_dir: data/artifacts
retry_count: 3
timeout_ms: 30000
headless: true
```

- `name` 必须与聊天列表显示的备注或昵称完全一致。
- 目标名称不得重复。存在同名好友时，先在抖音中设置不同备注。
- `retry_count` 为单个目标最大尝试次数，允许 1–5。
- 如需观察浏览器排错，把 `headless` 改为 `false`。

编辑 `messages.txt`，每行一条文案。空行会被忽略，重复文案会去重。所有文案使用一轮后才会重新洗牌。

校验配置：

```powershell
autody check-config
```

## 首次扫码登录

```powershell
autody login
```

浏览器打开后扫码登录。工具检测到聊天列表后会保存登录状态并关闭浏览器。登录数据只保存在 `data/browser-profile`，不会写入日志或 Git。

## 首次真实测试

先只配置一位知情的测试好友，然后运行：

```powershell
autody run
```

当天再次执行同一命令应显示任务已完成，不会重复发送。确认后再添加其他目标。

退出码：

- `0`：当天所有目标完成，或之前已经完成。
- `2`：部分目标失败；再次运行只补发失败目标并复用当天文案。
- `3`：登录失效、安全验证或页面结构变化；任务已安全停止。

## 每天 07:30 自动运行

```powershell
.\scripts\install-task.ps1
Get-ScheduledTask -TaskName AutoDy-DailySpark
```

计划任务使用 Windows 本地时间，每天 07:30 运行；电脑错过时间后会在下次可运行时尽快补跑，且不会并行启动两个实例。工具自身的当天状态会防止重复发送。

删除计划任务：

```powershell
.\scripts\remove-task.ps1
```

## 数据与故障排查

- `data/state.json`：当天文案、成功目标和文案轮换状态。
- `data/logs/autody.log`：运行日志，保留 14 天。
- `data/artifacts/`：失败页面截图。
- `data/browser-profile/`：抖音登录状态，视为敏感数据，不要分享。

常见问题：

1. **提示重新登录或出现安全验证**：运行 `autody login`，在可见浏览器中由本人完成验证。工具不会自动绕过。
2. **找不到好友**：确认配置名称与聊天列表完全一致；聊天列表需要能在网页版显示该会话。
3. **同名歧义**：在抖音中为好友设置唯一备注后修改配置。
4. **页面结构变化**：查看 `data/artifacts` 截图。页面定位集中在 `src/autody/chat.py` 的 `DOUYIN_SELECTORS`；当前会话列表和输入框选择器参考了 DouYinSparkFlow `dev` 分支。
5. **状态文件损坏**：工具会停止，不会按空状态继续发送。备份损坏文件后再人工判断是否重建，避免当天重复发送。
6. **任务没有运行**：执行 `Get-ScheduledTaskInfo -TaskName AutoDy-DailySpark` 查看最近结果，并确认 `.venv` 和项目目录未移动。

## 测试

```powershell
pytest -v
```

浏览器自动测试只打开本地伪聊天页面，不会连接抖音或发送真实消息。

## 来源与许可

本项目参考 [2061360308/DouYinSparkFlow](https://github.com/2061360308/DouYinSparkFlow) 的 Playwright 浏览器自动化思路，并基于其 `dev` 分支面向 `douyin.com/chat` 的方向重新实现。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [LICENSE](LICENSE)。
