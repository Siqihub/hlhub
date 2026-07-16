# AutoDy v1.1.1

- Reuses a valid project virtual environment instead of recreating it during normal installation updates.
- Stops only an identified project AutoDy service when an invalid environment must be repaired.
- Makes native installer failures stop the installation and return a non-zero exit code.
- Repairs Windows PowerShell 5.1 shortcut-script encoding compatibility and validates every tracked PowerShell script before portable packaging.

No local account, browser, cache, message, history, or log data is included in source or portable artifacts.
