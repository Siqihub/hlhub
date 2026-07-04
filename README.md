# AutoDy 抖音每日续火助手

Windows 本地自动化工具：每天 07:30 从文案库随机选择一条本轮未使用的文案，发送给配置的抖音好友。同一天重复运行只补发失败目标。

![AutoDy 管理台](docs/images/dashboard.png)

## 主要功能

- 可视化管理好友、文案、任务计划、日志和备份
- 每天 07:20 检查登录，07:30 自动发送，每周日 20:00 再次检查
- 60 条带符号、多风格的内置文案，整轮使用前不重复
- 失败目标单独补发，避免当天重复发送成功目标
- 登录失效时弹出 Windows 提醒，并在桌面生成重新登录入口
- 安全备份和跨电脑迁移；不会导出 Cookie 或浏览器登录目录
- GitHub Actions 自动测试，并在版本标签发布 Windows 便携包

> 仅用于个人低频、自用场景。抖音页面和登录策略可能变化，使用者需遵守平台规则并自行承担账号风险。本工具不会绕过验证码或安全验证。

## 最快安装

环境要求：Windows 10/11、Python 3.11 或更高版本。

1. 下载并解压 `AutoDy-Windows-Portable.zip`。
2. 双击 `install.cmd`。
3. 安装完成后，打开桌面的 `AutoDy-管理台.cmd`。
4. 在管理台配置好友，点击“扫码登录”，再安装定时任务。

安装器会自动创建 Python 虚拟环境、安装 Chromium、生成本地配置和桌面入口。以后复制整个目录到另一台电脑，重新运行 `install.cmd` 即可。

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
autody doctor
autody repair-playwright
autody run
autody ui
```

退出码：

- `0`：当天全部完成，或此前已经完成
- `2`：部分失败；再次运行只补发失败目标
- `3`：登录失效、安全验证或页面结构变化，任务安全停止

## 定时任务

```powershell
.\scripts\install-task.ps1
Get-ScheduledTask -TaskName AutoDy-DailySpark
```

安装后的任务：

- `AutoDy-Health-Daily`：每天 07:20 检查登录
- `AutoDy-DailySpark`：每天 07:30 发送
- `AutoDy-Health-Weekly`：每周日 20:00 检查登录

电脑错过时间后会在下次可运行时尽快补跑，且不会并行执行。登录失效或任务异常时，桌面会出现 `AutoDy-需要处理.txt` 和 `AutoDy-重新登录.cmd`。

删除任务：

```powershell
.\scripts\remove-task.ps1
```

## 备份与迁移

管理台“备份迁移”页面可导出 ZIP，包含：

- 好友配置
- 文案库
- 文案轮换和当日发送状态

备份明确排除 `data/browser-profile`。换电脑后导入备份，仍需本人重新扫码登录。

## 数据与排错

- `data/state.json`：每日发送和文案轮换状态
- `data/logs/autody-YYYY-MM-DD.log`：按日期生成的应用日志，不做 Windows 文件重命名轮转
- `data/logs/scheduler.log`：计划任务日志
- `data/artifacts/`：失败页面截图
- `data/browser-profile/`：抖音登录状态，敏感且不进入 Git

常见处理：

1. 登录失效：双击桌面 `AutoDy-重新登录.cmd`。
2. 找不到好友：核对抖音聊天列表中的完整备注。
3. 页面结构变化：查看 `data/artifacts`，再更新 `src/autody/chat.py` 中的选择器。
4. 任务未运行：执行 `Get-ScheduledTaskInfo -TaskName AutoDy-DailySpark`。
5. Chromium 路径异常：执行 `autody doctor`；需要修复时执行 `autody repair-playwright`。浏览器固定安装在 `data/ms-playwright`。

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
