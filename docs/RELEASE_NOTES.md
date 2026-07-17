# AutoDy v1.2.0

- 普通总览和好友管理恢复为稳定的日常管理界面；测试功能移入可选测试中心。
- 新增官方可选模块 `autody-test-center` 1.0.0，通过“设置 > 可选模块”安装并在 iframe 中隔离运行。
- 模块包增加校验、路径限制、原子安装和安全卸载；模块数据只保存在 `data/modules/autody-test-center`。
- 源码安装会重建前端，入口页面禁止缓存旧 HTML；便携包不要求 Node.js。

- Repairs the desktop dashboard launcher for Windows command-shell encoding and quoting.
- Waits for the local dashboard identity endpoint before opening the browser.
- Reuses the verified current AutoDy service, stops only a confirmed stale AutoDy listener, and reports unrelated port conflicts without terminating them.
- Keeps launcher failures visible with a safe local diagnostic log.

No local account, browser, cache, message, history, or log data is included in source or portable artifacts.
