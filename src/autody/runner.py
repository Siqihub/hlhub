from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import hashlib
import logging
import random
import time

from autody.chat import DeliveryResult, DeliveryStatus, FatalChatError
from autody.config import AppConfig
from autody.history import TaskHistoryStore, TaskRunRecord, stable_target_id
from autody.messages import MessageRotation, format_message_with_suffix, read_messages
from autody.state import StateStore


logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    ALREADY_DONE = "already_done"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    BLOCKED = "blocked"
    BLOCKED_AMBIGUOUS_TARGET = "blocked_ambiguous_target"


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    total_targets: int
    sent_count: int
    skipped_count: int
    failed_count: int
    error: str | None = None
    run_id: str | None = None
    retry_count: int = 0
    confirmation_results: dict[str, str] = field(default_factory=dict)


def _history_path(config: AppConfig):
    return config.state_file.parent / "history" / "task-runs.jsonl"


def _delivery_result(value) -> DeliveryResult:
    if isinstance(value, DeliveryResult):
        return value
    return DeliveryResult(DeliveryStatus.CONFIRMED, send_attempts=1, confirmation_attempts=1)


def _record_history(
    config: AppConfig,
    started: datetime,
    source: str,
    result: RunResult,
    base_message: str,
    failed_names: list[str],
) -> None:
    ended = datetime.now(started.tzinfo)
    TaskHistoryStore(_history_path(config)).append(
        TaskRunRecord(
            run_id=result.run_id or hashlib.sha256(started.isoformat().encode()).hexdigest()[:24],
            date=started.date().isoformat(),
            task_type="daily_send",
            trigger_source=source,  # type: ignore[arg-type]
            start_time=started.isoformat(timespec="seconds"),
            end_time=ended.isoformat(timespec="seconds"),
            duration=max(0.0, (ended - started).total_seconds()),
            total_targets=result.total_targets,
            success_count=result.sent_count,
            failed_count=result.failed_count,
            skipped_count=result.skipped_count,
            retry_count=result.retry_count,
            final_status=result.status.value,
            base_message_id=hashlib.sha256(base_message.encode("utf-8")).hexdigest()[:16] if base_message else None,
            message_pack="global",
            error_summary=(result.error or "")[:240] or None,
            failed_target_ids=[stable_target_id(name) for name in failed_names],
            confirmation_results=result.confirmation_results,
        )
    )


def run_daily(
    config: AppConfig,
    chat,
    today: date | None = None,
    *,
    trigger_source: str = "manual",
    now: datetime | None = None,
) -> RunResult:
    started = now or datetime.now()
    today = today or started.date()
    key = today.isoformat()
    store = StateStore(config.state_file)
    rotation = MessageRotation()
    state = store.load()
    daily = state.daily.setdefault(
        key,
        {
            "message": "",
            "succeeded": [],
            "failures": {},
            "confirmation_results": {},
            "consumed": False,
        },
    )
    daily.setdefault("confirmation_results", {})
    targets = [target for target in config.targets if target.enabled]
    if config.friend_order == "randomized":
        random.SystemRandom().shuffle(targets)
    normalized_names = {}
    for target in targets:
        normalized_names.setdefault(" ".join(target.name.split()).casefold(), []).append(target)
    ambiguous_names = {
        name
        for name, grouped_targets in normalized_names.items()
        if len(grouped_targets) > 1
    }
    ambiguous_targets = [
        target for target in targets
        if " ".join(target.name.split()).casefold() in ambiguous_names
    ]
    for target in ambiguous_targets:
        daily["failures"][target.name] = "blocked_ambiguous_target"
    pending = [
        target.name for target in targets
        if target.name not in daily["succeeded"]
        and " ".join(target.name.split()).casefold() not in ambiguous_names
    ]
    total = len(targets)
    skipped = total - len(pending)
    run_id = hashlib.sha256(f"{started.isoformat()}:{key}:{trigger_source}".encode()).hexdigest()[:24]
    if not pending:
        status = RunStatus.BLOCKED_AMBIGUOUS_TARGET if ambiguous_targets else RunStatus.ALREADY_DONE
        result = RunResult(status, total, 0, skipped, len(ambiguous_targets), "blocked_ambiguous_target" if ambiguous_targets else None, run_id=run_id)
        _record_history(config, started, trigger_source, result, daily.get("message", ""), [])
        return result
    if skipped and trigger_source == "manual":
        trigger_source = "retry"

    messages = read_messages(config.messages_file)
    if not daily["message"]:
        daily["message"] = rotation.peek(messages, state.rotation)
        store.save(state)
    outgoing_message = format_message_with_suffix(daily["message"], config.message_suffix)
    daily.setdefault("messages_by_target", {})

    sent = 0
    retries = 0
    confirmation_results: dict[str, str] = {}
    blocked_error: str | None = None
    for target_index, target in enumerate(pending):
        target_message = outgoing_message
        if config.message_selection == "per_friend":
            base = daily["messages_by_target"].get(target)
            if not base:
                base = random.SystemRandom().choice(messages)
                daily["messages_by_target"][target] = base
                store.save(state)
            target_message = format_message_with_suffix(base, config.message_suffix)
        target_id = stable_target_id(target)
        error = None
        for attempt in range(config.retry_count):
            if attempt:
                retries += 1
            try:
                delivery = _delivery_result(chat.send(target, target_message))
            except FatalChatError as exc:
                delivery = DeliveryResult(DeliveryStatus.BLOCKED, error=str(exc))
            except RuntimeError as exc:
                delivery = DeliveryResult(DeliveryStatus.SEND_FAILED, error=str(exc))
            confirmation_results[target_id] = delivery.status.value
            daily["confirmation_results"][target_id] = delivery.status.value
            retries += max(0, delivery.confirmation_attempts - 1)
            if delivery.successful:
                daily["succeeded"].append(target)
                daily["failures"].pop(target, None)
                sent += 1
                error = None
                logger.info("发送已确认：%s（%s）", target, delivery.status.value)
                break
            error = delivery.error or delivery.status.value
            if delivery.status is DeliveryStatus.BLOCKED:
                blocked_error = error
                break
            if delivery.status is DeliveryStatus.CONFIRMATION_FAILED:
                # The send may have reached Douyin even when DOM confirmation is
                # unavailable. Never press Enter again in the same run. A later
                # run first checks the latest bubble and can safely mark success.
                break
            logger.warning(
                "发送未确认：%s（第 %s/%s 次，%s）：%s",
                target,
                attempt + 1,
                config.retry_count,
                delivery.status.value,
                error,
            )
            if attempt + 1 < config.retry_count:
                time.sleep(random.uniform(1, 3))
        if error:
            daily["failures"][target] = error
        store.save(state)
        if blocked_error:
            break
        if target_index < len(pending) - 1:
            time.sleep(random.uniform(config.min_delay_seconds, config.max_delay_seconds))

    complete = all(target.name in daily["succeeded"] for target in targets)
    if complete and not daily.get("consumed"):
        rotation.consume(daily["message"], state.rotation)
        daily["consumed"] = True
        store.save(state)
    failed_names = [target.name for target in targets if target.name not in daily["succeeded"]]
    status = (
        RunStatus.BLOCKED_AMBIGUOUS_TARGET if ambiguous_targets
        else RunStatus.BLOCKED if blocked_error
        else RunStatus.COMPLETED if complete
        else RunStatus.PARTIAL_FAILED
    )
    result = RunResult(
        status,
        total,
        sent,
        skipped,
        len(failed_names),
        blocked_error,
        run_id,
        retries,
        confirmation_results,
    )
    _record_history(config, started, trigger_source, result, daily["message"], failed_names)
    return result
