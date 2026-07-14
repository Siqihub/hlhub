# AutoDy 抖音每日续火助手

Windows 本地自动化工具：每天 07:30 从文案库随机选择一条本轮未使用的文案，发送给配置的抖音好友。同一天重复运行只补发失败目标。

![AutoDy 管理台](docs/images/dashboard.png)

## 主要功能

- 可视化管理好友、文案、在线文案包、任务计划、日志和备份
- 每天 07:20 检查登录，07:30 自动发送，每周日 20:00 再次检查
- 5 个公共示例文案包、共 250 条短问候，支持 GitHub 更新与离线回退
- 可配置 `gpt小助手` 动态后缀，不修改文案库原文
- 登录后可自动识别聊天列表候选好友，确认后再加入配置
- 失败目标单独补发，避免当天重复发送成功目标
- 发送后核对当前会话最新的我方消息气泡，最终文案完全匹配后才记录成功
- 错过每日时间后，在管理台启动或健康检查时执行一次同日恢复
- 轻量 JSONL 运行历史、成功率统计和可筛选的脱敏日志中心
- 登录失效时在管理台“需要处理”区域集中提示
- 安全备份和跨电脑迁移；不会导出 Cookie 或浏览器登录目录
- GitHub Actions 自动测试，并在版本标签发布 Windows 便携包

> 仅用于个人低频、自用场景。抖音页面和登录策略可能变化，使用者需遵守平台规则并自行承担账号风险。本工具不会绕过验证码或安全验证。

## 最快安装

环境要求：Windows 10/11、Python 3.11 或更高版本。

1. 下载并解压 `AutoDy-Windows-Portable.zip`。
2. 双击 `install.cmd`。
3. 安装完成后，打开桌面的 `AutoDy 管理台` 快捷方式。
4. 在管理台配置好友，点击“扫码登录”，再安装定时任务。

安装器会自动创建 Python 虚拟环境、安装项目专用 Chromium、生成本地配置，并创建带自定义图标的 `.lnk` 桌面入口。

`install.cmd` 只用于首次安装、重装、移动到另一台电脑或修复环境。日常使用只需双击桌面的 `AutoDy 管理台`，不需要重复安装。

## 开发安装

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item config.example.yaml config.yaml
Copy-Item messages.example.txt messages.txt
.\.venv\Scripts\autody.exe ui
```

管理台只监听 `127.0.0.1:8765`，不会暴露到局域网。

前端开发：

```powershell
cd frontend
npm install
npm run dev
```

前端生产构建会写入 Python 包中的 `src/autody/web/static`：

```powershell
cd frontend
npm run build
```

## 配置与运行

好友名称必须与抖音聊天列表中的备注或昵称完全一致。存在同名好友时，应先设置唯一备注。

```powershell
autody check-config
autody login
autody health-check
autody scan-friends
autody doctor
autody repair-playwright
autody run
autody ui
```

退出码：

- `0`：当天全部完成，或此前已经完成
- `2`：部分失败；再次运行只补发失败目标
- `3`：登录失效、安全验证或页面结构变化，任务安全停止

## 在线文案库

管理台“在线文案库”可以预览、合并或替换公共示例文案包：

- 合并：保留当前文案，添加未重复的新文案。
- 替换：用文案包替换当前文案。
- 两种写入模式都会先备份到 `data/backups/messages-<时间>.txt`。
- 网络失败时自动回退到仓库内置的 `message-packs/`。

当前仓库尚未配置 Git remote，`message-packs/index.json` 使用相对路径。推送 GitHub 后，在管理台设置页或 `config.yaml` 中填写：

```yaml
message_pack_index_url: "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/message-packs/index.json"
```

服务会用索引 URL 和 `relative_url` 自动定位各文本包；也可把索引内每项的 `raw_url` 更新为对应的 `raw.githubusercontent.com` 完整地址。公共 `message-packs` 只是示例，导入发生在本机，个人 `messages.txt` 不会同步到 GitHub。

## 消息后缀

默认配置为：

```yaml
message_suffix:
  enabled: true
  text: "gpt小助手"
  style: dash
```

支持 `dash`、`bracket`、`newline`、`none` 四种样式。后缀只在发送瞬间动态添加；`messages.txt`、文案轮换和每日状态始终记录基础文案。管理台设置页提供实时预览。

## 自动识别好友

登录抖音后，在“好友管理”点击“自动识别好友”。AutoDy 通过 DOM 读取并有限滚动聊天列表，将去重后的候选保存到 `data/discovered_friends.json`。它不会覆盖现有好友，也不会自动添加全部候选；选择候选并点击添加后，仍需保存配置。

## 定时任务

```powershell
.\scripts\install-task.ps1
Get-ScheduledTask -TaskName AutoDy-DailySpark
```

安装后的任务：

- `AutoDy-Health-Daily`：每天 07:20 检查登录
- `AutoDy-DailySpark`：每天 07:30 发送
- `AutoDy-Health-Weekly`：每周日 20:00 检查登录

电脑错过时间后会在下次可运行时尽快补跑，且不会并行执行。登录失效或任务异常时，内部通知写入 `data/notifications/need-attention.txt`，桌面不再散落辅助 CMD/TXT 文件；处理入口统一在管理台。

应用层还会在管理台启动和健康检查时检查今日状态。只有当前时间已超过 `daily_send_time`、未超过 `recovery_deadline` 且今日仍有未完成目标时，才启动一次 `startup_recovery`。恢复任务与定时任务共用全局锁，并沿用同日成功名单，因此不会重发已完成目标。

管理台“定时任务”页可编辑每日/每周检查时间、发送时间、启动恢复开关与当日截止时间。应用前会预览旧值、新值和受影响的 Windows 任务；如果任务更新失败，会保留旧配置并恢复旧任务。旧 `config.yaml` 仍可直接使用，新增项都有安全默认值：

```yaml
daily_send_time: "07:30"
daily_health_check_time: "07:20"
weekly_health_check_enabled: true
startup_recovery_enabled: true
recovery_deadline: "23:59"
mask_log_friend_names: true
```

发送确认失败时会保存截图和结构化结果，但同一次运行不会再次按 Enter。稍后补发会先检查最新我方气泡；如果消息实际已经存在，只登记成功，不重复发送。

删除任务：

```powershell
.\scripts\remove-task.ps1
```

## 备份与迁移

管理台“备份迁移”页面可选择导出 ZIP 类别：

- 好友配置
- 文案库
- 后缀、计划、发送行为、文案包和非敏感应用设置
- 可选的文案轮换和当日发送状态

新备份使用带版本、类别和 SHA-256 校验和的 manifest。导入前会预检路径、可执行文件、冲突和设置变化；支持合并/替换，并会先在 `data/backups/` 创建本地回滚备份。备份明确排除 `data/browser-profile`、Cookie、令牌、日志和截图。换电脑后导入备份，仍需本人重新扫码登录。

## 数据与排错

- `data/state.json`：每日发送和文案轮换状态
- `data/logs/autody-YYYY-MM-DD.log`：按日期生成的应用日志，不做 Windows 文件重命名轮转
- `data/logs/scheduler.log`：计划任务日志
- `data/history/task-runs.jsonl`：不保存完整好友姓名和完整文案的轻量运行记录
- `data/logs/archive/`：通过管理台“归档旧日志”移动的历史日志，不会静默删除
- `data/artifacts/`：失败页面截图
- `data/browser-profile/`：抖音登录状态，敏感且不进入 Git
- `data/discovered_friends.json`：最近一次候选好友扫描结果
- `data/notifications/need-attention.txt`：管理台待处理通知

常见处理：

1. 登录失效：打开桌面的 `AutoDy 管理台`，点击“扫码登录”。
2. 找不到好友：核对抖音聊天列表中的完整备注。
3. 页面结构变化：查看 `data/artifacts`，再更新 `src/autody/chat.py` 中的选择器。
4. 任务未运行：执行 `Get-ScheduledTaskInfo -TaskName AutoDy-DailySpark`。
5. Chromium 路径异常：执行 `autody doctor`；需要修复时执行 `autody repair-playwright`。浏览器固定安装在 `data/ms-playwright`。

管理台日志页默认只读取最近三天，支持日期、级别、任务和“当前/已解决/历史”过滤；旧版 `autody.log.YYYY-MM-DD` 仍可查看。相同 traceback 会按稳定指纹分组，Python traceback 默认折叠，好友名称默认显示为稳定的 `好友#xxxx`，可在设置中关闭脱敏。可归档历史日志、导出脱敏诊断包、打开本地日志目录或复制精简错误摘要。总览中的连续成功天数、7/30 天成功率和重试次数来自 JSONL 运行记录，不会在首页解析全部日志。

## 隐私边界

以下本地数据绝不能上传或提交到 GitHub：

- `config.yaml`
- `messages.txt`
- `data/browser-profile`、Cookie 和登录状态
- 日志、失败截图、下载文件和候选好友
- `.venv`

仓库公开内容只包括程序代码、文档、图标和通用 `message-packs` 示例。备份与文案包导入也都在本机完成。

## 测试与发布

```powershell
.\.venv\Scripts\pytest.exe -q
cd frontend
npm test
npm run build
cd ..
.\scripts\build-portable.ps1
```

浏览器测试只打开本地伪聊天页面，不连接抖音，也不会发送真实消息。

推送 `v*` 标签后，GitHub Actions 会生成 Release，并上传 `AutoDy-Windows-Portable.zip`。

## 来源与许可

本项目参考 [2061360308/DouYinSparkFlow](https://github.com/2061360308/DouYinSparkFlow) 的 Playwright 浏览器自动化思路，并面向 `douyin.com/chat` 重新实现。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [LICENSE](LICENSE)。
