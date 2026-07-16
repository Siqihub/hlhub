# AutoDy v1.1.0

- Adds a structured failed-target center and strict safe-retry boundary.
- Adds target-specific message, suffix, order and delay settings.
- Adds a read-only today sending plan and an environment status center.
- Includes read-only send preflight, account/avatar support, log retention and launcher corrections.
- Excludes local account, browser, cache and log data from source and portable artifacts.

Known limitation: platform page changes can make browser checks unavailable. AutoDy stops safely and records the reason rather than guessing a send result.
