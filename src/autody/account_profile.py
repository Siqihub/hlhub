"""Verified local cache for the authenticated Douyin account.

This module intentionally reads only the page's explicit current-login store.
It never inspects friend candidates, conversation rows, or message content.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path

from PIL import Image


class AccountProfileUnavailable(RuntimeError):
    """The page did not provide a verifiable authenticated account object."""


@dataclass(frozen=True)
class AccountProfile:
    account_profile_id: str
    account_id_digest: str
    display_name: str
    avatar_cache_key: str
    avatar_version: str
    is_self: bool
    verification_source: str
    profile_status: str
    verified_at: str
    last_updated_at: str
    switched: bool = False


def _paths(root: Path) -> tuple[Path, Path]:
    data = root / "data"
    return data / "account-profile.json", data / "account-avatar" / "profile.png"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def load_account_profile(root: Path) -> AccountProfile | None:
    path, avatar = _paths(root)
    if not path.is_file() or not avatar.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("profile_status") != "verified" or payload.get("is_self") is not True:
            return None
        return AccountProfile(**{key: payload[key] for key in AccountProfile.__dataclass_fields__ if key in payload})
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _current_user_from_page(page) -> dict | None:
    # The object name was verified in a real, authenticated Douyin chat session.
    # Its `curLoginUserInfo` ownership is the strong self-user semantic; fields
    # are extracted together from that one object.
    return page.evaluate(
        """() => {
          const user = globalThis.userInfoStore?.curLoginUserInfo;
          if (!user || typeof user !== 'object') return null;
          const stableId = user.secUid || user.sec_uid || user.uid;
          const nickname = user.nickname;
          const avatar = user.avatarUrl || user.avatar300Url ||
            user.avatarThumb?.urlList?.[0] || user.avatar?.urlList?.[0] ||
            user.avatarLarger?.urlList?.[0];
          if (typeof stableId !== 'string' && typeof stableId !== 'number') return null;
          if (typeof nickname !== 'string' || !nickname.trim()) return null;
          if (typeof avatar !== 'string' || !avatar.startsWith('http')) return null;
          return {
            stable_id: String(stableId), display_name: nickname.trim(), avatar_url: avatar,
            source: 'bootstrap_current_login_user', is_self: true
          };
        }"""
    )


def attach_account_observer(page) -> None:
    """Attach read-only login-flow observers before navigation or QR completion.

    Response bodies are deliberately not persisted.  The verified bootstrap store
    remains the source of truth because it explicitly denotes the current login.
    """
    def observe_response(response) -> None:
        content_type = str(response.headers.get("content-type", "")).lower()
        if "json" not in content_type:
            return
        # Parse only to confirm that the listener observes JSON traffic.  Never
        # retain raw objects, URLs, cookies, or identifiers from network data.
        try:
            response.json()
        except Exception:
            return

    page.on("response", observe_response)
    page.on("framenavigated", lambda _frame: None)


def _download_avatar(page, url: str, destination: Path) -> str:
    response = page.context.request.get(url, timeout=10_000)
    content_type = str(getattr(response, "headers", {}).get("content-type", "")).lower()
    if not getattr(response, "ok", False) or not content_type.startswith("image/"):
        raise AccountProfileUnavailable("当前账号头像下载未通过图片校验")
    raw = response.body()
    try:
        image = Image.open(BytesIO(raw))
        image.verify()
        image = Image.open(BytesIO(raw)).convert("RGBA")
        if image.width < 1 or image.height < 1:
            raise ValueError("empty image")
    except Exception as exc:
        raise AccountProfileUnavailable("当前账号头像文件无效") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.png")
    image.save(temporary, format="PNG")
    content = temporary.read_bytes()
    os.replace(temporary, destination)
    return sha256(content).hexdigest()[:20]


def resolve_account_profile(page, root: Path, now=None) -> AccountProfile:
    """Resolve and persist one verified current-account record from a page."""
    candidate = _current_user_from_page(page)
    if not isinstance(candidate, dict) or candidate.get("is_self") is not True:
        raise AccountProfileUnavailable("未发现可验证的当前登录账号资料")
    stable_id = str(candidate.get("stable_id", "")).strip()
    display_name = str(candidate.get("display_name", "")).strip()
    avatar_url = str(candidate.get("avatar_url", "")).strip()
    if not stable_id or not display_name or not avatar_url.startswith(("https://", "http://")):
        raise AccountProfileUnavailable("当前登录账号资料不完整")

    profile_path, avatar_path = _paths(root)
    previous = load_account_profile(root)
    digest = sha256(stable_id.encode("utf-8")).hexdigest()
    timestamp = (now or datetime.now)().isoformat(timespec="seconds")
    # Download before replacing metadata so an incomplete switch can never mix a
    # new nickname with the previous account's avatar.
    avatar_version = _download_avatar(page, avatar_url, avatar_path)
    switched = bool(previous and previous.account_id_digest != digest)
    profile = AccountProfile(
        account_profile_id=f"account-{digest[:24]}",
        account_id_digest=digest,
        display_name=display_name,
        avatar_cache_key="profile",
        avatar_version=avatar_version,
        is_self=True,
        verification_source="bootstrap_current_login_user",
        profile_status="verified",
        verified_at=timestamp,
        last_updated_at=timestamp,
        switched=switched,
    )
    payload = asdict(profile)
    if switched:
        payload["switch_audit"] = [{
            "at": timestamp,
            "from_account_id_digest": previous.account_id_digest,
            "to_account_id_digest": digest,
        }]
    # Do not persist remote URLs (which may contain short-lived signatures).
    payload["avatar_source"] = "authenticated_browser_image"
    _atomic_json(profile_path, payload)
    return profile


def public_profile_payload(root: Path, logged_in: bool = False, refresh_running: bool = False) -> dict:
    profile = load_account_profile(root)
    if profile is None:
        return {
            "display_name": None, "avatar_url": None, "avatar_version": None,
            "is_self": False, "profile_status": "unverified", "verification_source": None,
            "logged_in": logged_in, "cached": False, "last_updated_at": None,
            "refresh_running": refresh_running,
        }
    return {
        "display_name": profile.display_name,
        "avatar_url": f"/api/account-profile/avatar?v={profile.avatar_version}",
        "avatar_version": profile.avatar_version,
        "is_self": True,
        "profile_status": "verified",
        "verification_source": profile.verification_source,
        "logged_in": logged_in,
        "cached": True,
        "last_updated_at": profile.last_updated_at,
        "refresh_running": refresh_running,
    }
