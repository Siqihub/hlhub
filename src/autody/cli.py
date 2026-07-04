import logging
from pathlib import Path
import threading
import webbrowser

import typer
import uvicorn

from autody.chat import DOUYIN_SELECTORS, DouyinChat, FatalChatError, login as browser_login, open_chat
from autody.config import AppConfig, load_config
from autody.friend_discovery import discover_friends
from autody.locking import SingleInstanceLock, TaskAlreadyRunning
from autody.logging_setup import setup_logging
from autody.messages import read_messages
from autody.runner import RunStatus, run_daily
from autody.runtime import configure_runtime, doctor_playwright, repair_playwright
from autody.web_api import create_app


app = typer.Typer(no_args_is_help=True, help="抖音每日续火花工具")


BUSY_MESSAGE = "已有 AutoDy 任务正在运行，本次跳过。"


def _project_root(config_path: Path) -> Path:
    return config_path.resolve().parent


def _busy() -> None:
    typer.echo(BUSY_MESSAGE)


@app.command("check-config")
def check_config(config: Path = typer.Option(Path("config.yaml"), "--config")):
    loaded = load_config(config)
    if not loaded.messages_file.exists():
        raise typer.BadParameter("文案库不存在")
    messages = read_messages(loaded.messages_file)
    typer.echo(f"配置有效：{len(loaded.targets)} 个目标，{len(messages)} 条文案")


@app.command()
def login(config: Path = typer.Option(Path("config.yaml"), "--config")):
    loaded = load_config(config)
    try:
        with SingleInstanceLock(loaded.lock_file):
            configure_runtime(_project_root(config))
            typer.echo("浏览器将打开，请扫码登录；检测到聊天列表后会自动保存并关闭。")
            browser_login(loaded.profile_dir, home=_project_root(config))
            typer.echo("登录状态已保存。")
    except TaskAlreadyRunning:
        _busy()


@app.command("health-check")
def health_check(config: Path = typer.Option(Path("config.yaml"), "--config")):
    loaded = load_config(config)
    try:
        with SingleInstanceLock(loaded.lock_file):
            configure_runtime(_project_root(config))
            setup_logging(loaded)
            with open_chat(
                loaded.profile_dir,
                loaded.timeout_ms,
                True,
                loaded.artifact_dir,
                home=_project_root(config),
            ):
                logging.info("登录状态和抖音聊天页正常。")
    except TaskAlreadyRunning:
        _busy()
        return
    except FatalChatError as exc:
        logging.error("登录健康检查失败：%s", exc)
        typer.echo(f"登录健康检查失败：{exc}", err=True)
        raise typer.Exit(3) from exc
    except Exception:
        logging.exception("登录健康检查发生未捕获异常。")
        typer.echo("登录健康检查发生未捕获异常，请查看当天日志。", err=True)
        raise typer.Exit(1)
    typer.echo("登录状态正常，聊天页可用。")


@app.command("scan-friends")
def scan_friends(config: Path = typer.Option(Path("config.yaml"), "--config")):
    loaded = load_config(config)
    try:
        with SingleInstanceLock(loaded.lock_file):
            configure_runtime(_project_root(config))
            setup_logging(loaded)
            with open_chat(
                loaded.profile_dir,
                loaded.timeout_ms,
                True,
                loaded.artifact_dir,
                home=_project_root(config),
            ) as page:
                result = discover_friends(
                    loaded,
                    page,
                    DOUYIN_SELECTORS,
                    loaded.state_file.parent / "discovered_friends.json",
                )
            logging.info("好友识别完成：发现 %s 个候选", len(result.candidates))
            typer.echo(f"好友识别完成：发现 {len(result.candidates)} 个候选。")
    except TaskAlreadyRunning:
        _busy()
    except FatalChatError as exc:
        logging.error("好友识别失败：%s", exc)
        typer.echo(f"好友识别失败：{exc}", err=True)
        raise typer.Exit(3) from exc
    except Exception:
        logging.exception("好友识别发生未捕获异常。")
        typer.echo("好友识别失败，请查看当天日志。", err=True)
        raise typer.Exit(1)


@app.command()
def doctor(config: Path = typer.Option(Path("config.yaml"), "--config")):
    loaded = load_config(config)
    try:
        with SingleInstanceLock(loaded.lock_file):
            result = doctor_playwright(_project_root(config))
    except TaskAlreadyRunning:
        _busy()
        return
    except RuntimeError as exc:
        runtime = configure_runtime(_project_root(config))
        typer.echo(f"Playwright 浏览器目录：{runtime.browsers_path}")
        typer.echo(f"Chromium 启动检查失败：{exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"AUTODY_HOME：{result.home}")
    typer.echo(f"Playwright 浏览器目录：{result.browsers_path}")
    typer.echo(f"Chromium 可执行文件：{result.executable_path}")
    typer.echo("Chromium 启动检查：成功")


@app.command("repair-playwright")
def repair_playwright_command(
    config: Path = typer.Option(Path("config.yaml"), "--config")
):
    loaded = load_config(config)
    try:
        with SingleInstanceLock(loaded.lock_file):
            runtime = repair_playwright(_project_root(config))
    except TaskAlreadyRunning:
        _busy()
        return
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Chromium 已重新安装到：{runtime.browsers_path}")


@app.command()
def ui(
    config: Path = typer.Option(Path("config.yaml"), "--config"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
    no_open: bool = typer.Option(False, "--no-open"),
):
    config = config.resolve()
    load_config(config)
    configure_runtime(config.parent)
    if host not in {"127.0.0.1", "localhost"}:
        raise typer.BadParameter("管理台只能监听本机地址")
    url = f"http://127.0.0.1:{port}"
    if not no_open:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    typer.echo(f"AutoDy 管理台正在运行：{url}")
    uvicorn.run(create_app(config), host="127.0.0.1", port=port, log_level="warning")


@app.command()
def run(config: Path = typer.Option(Path("config.yaml"), "--config")):
    loaded = load_config(config)
    try:
        with SingleInstanceLock(loaded.lock_file):
            configure_runtime(_project_root(config))
            setup_logging(loaded)
            with open_chat(
                loaded.profile_dir,
                loaded.timeout_ms,
                loaded.headless,
                loaded.artifact_dir,
                home=_project_root(config),
            ) as page:
                chat = DouyinChat(page, DOUYIN_SELECTORS, loaded.artifact_dir)
                result = run_daily(loaded, chat)
            if result.status is RunStatus.ALREADY_DONE:
                message = "当天所有目标此前已完成。"
            else:
                message = (
                    f"本次发送完成：成功 {result.sent_count} 个，"
                    f"失败 {result.failed_count} 个。"
                )
            logging.info(message)
            typer.echo(message)
            if result.status is RunStatus.PARTIAL_FAILED:
                detail = "本次部分失败，再次运行将只补发失败目标。"
                logging.error(detail)
                typer.echo(detail, err=True)
                raise typer.Exit(2)
            if result.status is RunStatus.BLOCKED:
                detail = f"浏览器任务已安全停止：{result.error or '页面被阻止'}"
                logging.error(detail)
                typer.echo(detail, err=True)
                raise typer.Exit(3)
    except TaskAlreadyRunning:
        _busy()
        return
    except FatalChatError as exc:
        logging.error("浏览器任务已安全停止：%s", exc)
        typer.echo(f"浏览器任务已安全停止：{exc}", err=True)
        raise typer.Exit(3) from exc
    except typer.Exit:
        raise
    except Exception:
        logging.exception("发送任务发生未捕获异常。")
        typer.echo("发送任务发生未捕获异常，请查看当天日志。", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
