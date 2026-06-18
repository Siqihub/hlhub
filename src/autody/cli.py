from logging.handlers import TimedRotatingFileHandler
import logging
from pathlib import Path

import typer

from autody.chat import DOUYIN_SELECTORS, DouyinChat, FatalChatError, login as browser_login, open_chat
from autody.config import AppConfig, load_config
from autody.messages import read_messages
from autody.runner import run_daily


app = typer.Typer(no_args_is_help=True, help="抖音每日续火花工具")


def setup_logging(config: AppConfig) -> None:
    log_dir = config.state_file.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if root.handlers:
        return
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = TimedRotatingFileHandler(
        log_dir / "autody.log", when="midnight", backupCount=14, encoding="utf-8"
    )
    stream_handler = logging.StreamHandler()
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


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
    typer.echo("浏览器将打开，请扫码登录；检测到聊天列表后会自动保存并关闭。")
    browser_login(loaded.profile_dir)
    typer.echo("登录状态已保存。")


@app.command()
def run(config: Path = typer.Option(Path("config.yaml"), "--config")):
    loaded = load_config(config)
    setup_logging(loaded)
    try:
        with open_chat(
            loaded.profile_dir,
            loaded.timeout_ms,
            loaded.headless,
            loaded.artifact_dir,
        ) as page:
            chat = DouyinChat(page, DOUYIN_SELECTORS, loaded.artifact_dir)
            if not run_daily(loaded, chat):
                logging.error("当天任务部分失败；再次运行只会补发失败目标。")
                raise typer.Exit(2)
    except FatalChatError as exc:
        logging.error("浏览器任务已安全停止：%s", exc)
        raise typer.Exit(3) from exc
    typer.echo("当天所有目标已完成。")


if __name__ == "__main__":
    app()
