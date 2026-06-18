from datetime import date
import logging
import random
import time

from autody.chat import FatalChatError
from autody.config import AppConfig
from autody.locking import SingleInstanceLock
from autody.messages import MessageRotation, read_messages
from autody.state import StateStore


logger = logging.getLogger(__name__)


def run_daily(config: AppConfig, chat, today: date | None = None) -> bool:
    today = today or date.today()
    key = today.isoformat()
    with SingleInstanceLock(config.lock_file):
        store = StateStore(config.state_file)
        rotation = MessageRotation()
        state = store.load()
        daily = state.daily.setdefault(
            key, {"message": "", "succeeded": [], "failures": {}, "consumed": False}
        )
        messages = read_messages(config.messages_file)
        if not daily["message"]:
            daily["message"] = rotation.peek(messages, state.rotation)
            store.save(state)

        pending = [
            target.name
            for target in config.targets
            if target.name not in daily["succeeded"]
        ]
        for target in pending:
            error = None
            for attempt in range(config.retry_count):
                try:
                    chat.send(target, daily["message"])
                    daily["succeeded"].append(target)
                    daily["failures"].pop(target, None)
                    error = None
                    logger.info("发送成功：%s", target)
                    break
                except FatalChatError:
                    store.save(state)
                    raise
                except RuntimeError as exc:
                    error = str(exc)
                    logger.warning(
                        "发送失败：%s（第 %s/%s 次）：%s",
                        target,
                        attempt + 1,
                        config.retry_count,
                        error,
                    )
                    if attempt + 1 < config.retry_count:
                        time.sleep(random.uniform(1, 3))
            if error:
                daily["failures"][target] = error
            store.save(state)

        complete = all(
            target.name in daily["succeeded"] for target in config.targets
        )
        if complete and not daily.get("consumed"):
            rotation.consume(daily["message"], state.rotation)
            daily["consumed"] = True
            store.save(state)
        return complete
