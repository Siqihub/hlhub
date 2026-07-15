from io import BytesIO
from pathlib import Path

from PIL import Image

from autody.account_profile import (
    AccountProfileUnavailable,
    load_account_profile,
    resolve_account_profile,
)


def _image_bytes(color: str) -> bytes:
    image = Image.new("RGB", (3, 3), color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class _Response:
    ok = True
    headers = {"content-type": "image/png"}

    def __init__(self, content: bytes):
        self._content = content

    def body(self):
        return self._content


class _Request:
    def __init__(self, content: bytes):
        self.content = content
        self.urls: list[str] = []

    def get(self, url: str, timeout: int):
        self.urls.append(url)
        return _Response(self.content)


class _Context:
    def __init__(self, content: bytes):
        self.request = _Request(content)


class _Page:
    def __init__(self, payload, content: bytes = b""):
        self.payload = payload
        self.context = _Context(content)

    def evaluate(self, _script):
        return self.payload


def _verified_user(name: str, stable_id: str, avatar_url: str = "https://image.example/avatar.png?token=secret"):
    return {
        "stable_id": stable_id,
        "display_name": name,
        "avatar_url": avatar_url,
        "source": "bootstrap_current_login_user",
        "is_self": True,
    }


def test_resolve_verified_current_user_writes_atomic_self_profile_and_local_avatar(tmp_path: Path):
    page = _Page(_verified_user("本人昵称", "current-user"), _image_bytes("red"))

    profile = resolve_account_profile(page, tmp_path)

    assert profile.is_self is True
    assert profile.display_name == "本人昵称"
    assert profile.verification_source == "bootstrap_current_login_user"
    assert not profile.account_id_digest.endswith("current-user")
    assert (tmp_path / "data" / "account-avatar" / "profile.png").is_file()
    assert load_account_profile(tmp_path) == profile
    assert "token=secret" not in (tmp_path / "data" / "account-profile.json").read_text(encoding="utf-8")


def test_unverified_or_chat_user_payload_cannot_create_a_profile(tmp_path: Path):
    page = _Page({"stable_id": "friend", "display_name": "聊天用户", "avatar_url": "https://image.example/friend.png", "is_self": False}, _image_bytes("blue"))

    try:
        resolve_account_profile(page, tmp_path)
    except AccountProfileUnavailable:
        pass
    else:
        raise AssertionError("chat-list user must not be accepted as the current account")

    assert load_account_profile(tmp_path) is None
    assert not (tmp_path / "data" / "account-avatar" / "profile.png").exists()


def test_account_switch_replaces_name_and_avatar_together(tmp_path: Path):
    first = resolve_account_profile(_Page(_verified_user("账号一", "user-one"), _image_bytes("red")), tmp_path)
    second = resolve_account_profile(_Page(_verified_user("账号二", "user-two"), _image_bytes("blue")), tmp_path)

    assert first.account_id_digest != second.account_id_digest
    assert second.display_name == "账号二"
    assert Image.open(tmp_path / "data" / "account-avatar" / "profile.png").getpixel((0, 0))[:3] == (0, 0, 255)
    stored = (tmp_path / "data" / "account-profile.json").read_text(encoding="utf-8")
    assert "账号一" not in stored
    assert "user-one" not in stored


def test_refresh_failure_preserves_the_previous_verified_profile(tmp_path: Path):
    original = resolve_account_profile(_Page(_verified_user("账号一", "user-one"), _image_bytes("red")), tmp_path)
    avatar = (tmp_path / "data" / "account-avatar" / "profile.png").read_bytes()

    try:
        resolve_account_profile(_Page({"stable_id": "friend", "display_name": "聊天用户", "is_self": False}), tmp_path)
    except AccountProfileUnavailable:
        pass
    else:
        raise AssertionError("unverified refresh must fail")

    assert load_account_profile(tmp_path) == original
    assert (tmp_path / "data" / "account-avatar" / "profile.png").read_bytes() == avatar
