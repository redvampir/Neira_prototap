from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

ACCESS_MODES = ("open", "whitelist", "admin_only")


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "y", "on"):
        return True
    if normalized in ("0", "false", "no", "n", "off"):
        return False
    return default


def _parse_access_mode(value: str | None, default: str) -> str:
    if value is None:
        return default
    normalized = value.strip().lower()
    return normalized if normalized in ACCESS_MODES else default


def _parse_channels(value: Any) -> set[int]:
    if value is None:
        return set()

    if isinstance(value, (list, tuple, set)):
        out: set[int] = set()
        for item in value:
            try:
                out.add(int(item))
            except (TypeError, ValueError):
                continue
        return out

    if isinstance(value, str):
        out: set[int] = set()
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.add(int(part))
            except ValueError:
                continue
        return out

    return set()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


@dataclass
class TelegramSettings:
    """Персистентные настройки Telegram-бота (без секретов)."""

    access_mode: str = "whitelist"
    allowed_channels: set[int] = field(default_factory=set)
    mention_only: bool = True

    def normalized(self) -> "TelegramSettings":
        access_mode = _parse_access_mode(self.access_mode, "whitelist")
        allowed_channels = _parse_channels(self.allowed_channels)
        mention_only = bool(self.mention_only)
        return TelegramSettings(
            access_mode=access_mode,
            allowed_channels=allowed_channels,
            mention_only=mention_only,
        )

    def to_json_dict(self) -> dict[str, Any]:
        s = self.normalized()
        return {
            "access_mode": s.access_mode,
            "allowed_channels": sorted(s.allowed_channels),
            "mention_only": s.mention_only,
        }


def load_telegram_settings(
    path: Path,
    *,
    env: Mapping[str, str] | None = None,
) -> TelegramSettings:
    """
    Загружает настройки из файла + применяет env override.

    Приоритет:
    1) переменные окружения, если ключ присутствует (даже если значение пустое)
    2) файл
    3) дефолты
    """
    env_map: Mapping[str, str] = os.environ if env is None else env
    file_data = _read_json(path)

    access_mode_file = file_data.get("access_mode")
    mention_only_file = file_data.get("mention_only")
    allowed_channels_file = file_data.get("allowed_channels")

    access_mode = _parse_access_mode(str(access_mode_file) if access_mode_file is not None else None, "whitelist")
    mention_only = _parse_bool(
        str(mention_only_file) if mention_only_file is not None else None,
        True,
    )
    allowed_channels = _parse_channels(allowed_channels_file)

    if "NEIRA_TG_ACCESS" in env_map:
        access_mode = _parse_access_mode(env_map.get("NEIRA_TG_ACCESS"), access_mode)
    if "NEIRA_TG_MENTION_ONLY" in env_map:
        mention_only = _parse_bool(env_map.get("NEIRA_TG_MENTION_ONLY"), mention_only)
    if "NEIRA_TG_CHANNELS" in env_map:
        allowed_channels = _parse_channels(env_map.get("NEIRA_TG_CHANNELS"))

    return TelegramSettings(
        access_mode=access_mode,
        allowed_channels=allowed_channels,
        mention_only=mention_only,
    ).normalized()


def save_telegram_settings(path: Path, settings: TelegramSettings) -> None:
    """Сохраняет настройки атомарно (защита от частичной записи)."""
    payload = json.dumps(settings.to_json_dict(), ensure_ascii=False, indent=2)
    _atomic_write_text(path, payload + "\n")

