# AutoDy

AutoDy 续火助手是一个仅在 Windows 本机运行的管理台，用于管理浏览器自动化、续火目标、文案库、定时任务和运行记录。所有账号资料、浏览器登录状态、好友缓存、头像、日志和个人文案均只保存在本机。

## 功能概览

- 可视化管理已配置目标和只读好友发现结果；昵称与头像按同一聊天列表行绑定。
- 支持文案库、内置文案包和发送后缀；每个目标可独立设置启用状态、备注、文案包、后缀、顺序和 0–30 分钟延迟。
- 每日定时登录检查与自动任务，同日成功记录不会重复发送；错过运行窗口时按既有保护规则恢复。
- 发送前自检、今日发送计划、今日异常目标和结构化运行统计。
- 发送结果不确定时禁止重试；只有能够确认尚未触发发送动作的失败才允许走原有保护流程重试。
- 可筛选、脱敏、按日期保存和可归档的日志中心；支持安全备份与迁移。
- 运行环境中心可查看本机服务身份、Chromium、登录、计划任务和运行状态，并提供安全修复入口。

发送前自检仅检查当前页面是否具备后续发送条件，不会输入或发送消息，也不保证平台最终投递成功。

## Windows 安装与首次启动

1. 下载并解压 `AutoDy-Windows-Portable.zip`。
2. 双击 `install.cmd`，安装项目专用 Python 环境和 Chromium。
3. 打开桌面的 `AutoDy 管理台` 快捷方式。
4. 在管理台中完成抖音登录、配置续火目标、检查文案库并安装定时任务。

安装器会创建项目内 `.venv`、`data/ms-playwright` 和稳定的桌面快捷方式。日常使用只需打开管理台；移动到新电脑后需重新登录。

## 使用说明

### 目标与好友发现

“好友管理”上方是当前续火目标。每张目标卡可打开“编辑目标设置”，保存只会影响该目标。下方候选来自本机缓存；点击候选即可加入目标，已加入候选会保留并显示状态。重复昵称会被明确标记，自动化不会猜测聊天对象。

### 今日计划与自检

总览中的“今日发送计划”显示主任务时间、执行顺序、目标延迟、有效文案来源、后缀、完成和阻止状态。加载或刷新计划是只读的：不会调用 Playwright、不会消耗文案、不会推进轮换状态、不会创建真实运行记录。

“发送前自检”仅检查聊天页是否具备后续发送条件。它不输入、不准备、不发送任何消息。

### 异常处理

“今日异常目标”来自结构化状态和任务历史，不依赖解析原始日志。确认失败、可能已触发发送或重名歧义都会显示为不确定并禁止重试。明确未发送的失败仍会复用全局锁、身份校验、同日去重和发送确认管线。

### 日志、备份与运行环境

日志按日期写入 `data/logs/`，可按日期、级别和状态筛选；保留策略支持预览、确认后整理和归档。备份不包含浏览器资料、Cookie、账号资料、头像、好友缓存或日志。运行环境页提供 Chromium 修复、登录、账号资料刷新和计划任务重建入口，不会覆盖 `config.yaml` 或删除浏览器资料。

## 定时任务

默认任务：

- `AutoDy-Health-Daily`：每日 07:20 登录健康检查。
- `AutoDy-DailySpark`：每日 07:30 主任务。
- `AutoDy-Health-Weekly`：每周日 20:00 健康检查。

Windows 任务使用 `IgnoreNew`，浏览器操作共用全局锁。每个目标的延迟由主任务内部处理，不会创建额外的 Windows 计划任务。

## 开发与验证

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m playwright install chromium
Copy-Item config.example.yaml config.yaml
Copy-Item messages.example.txt messages.txt
.\.venv\Scripts\python.exe -m autody.cli ui

.\.venv\Scripts\pytest.exe -q
cd frontend
npm ci
npm test
npm run build
cd ..
.\scripts\build-portable.ps1
```

管理台只监听 `127.0.0.1`。自动化测试使用本地伪页面和模拟记录，不会连接抖音或发送真实消息。

## 隐私与平台使用

不要提交或上传 `config.yaml`、`messages.txt`、`data/`、浏览器资料、Cookie、账号资料、头像、好友缓存、日志、截图、备份、`.venv` 或 `node_modules`。发布包只包含源代码、通用示例、安装脚本和公开文档。

本项目仅适用于低频本地个人使用。平台页面、登录和规则可能变化；请遵守平台规则，不要将其用于绕过验证、批量营销或未经授权的自动化。

## 许可与致谢

参见 [LICENSE](LICENSE) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

Maintained as part of the AutoDy Project.
