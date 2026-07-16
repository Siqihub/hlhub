# AutoDy v1.1.2

- Repairs the desktop dashboard launcher for Windows command-shell encoding and quoting.
- Waits for the local dashboard identity endpoint before opening the browser.
- Reuses the verified current AutoDy service, stops only a confirmed stale AutoDy listener, and reports unrelated port conflicts without terminating them.
- Keeps launcher failures visible with a safe local diagnostic log.

No local account, browser, cache, message, history, or log data is included in source or portable artifacts.
