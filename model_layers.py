from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_VERSION = 1
LAYER_KIND_OLLAMA_ADAPTER = "ollama_adapter"


class ModelLayersError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _as_non_empty_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelLayersError(f"Поле '{field_name}' должно быть непустой строкой.")
    return value.strip()


def _as_optional_str(value: Any, *, field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ModelLayersError(f"Поле '{field_name}' должно быть строкой или null.")
    trimmed = value.strip()
    return trimmed if trimmed else None


def _as_optional_float(value: Any, *, field_name: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ModelLayersError(f"Поле '{field_name}' должно быть числом или null.")
    if not isinstance(value, (int, float)):
        raise ModelLayersError(f"Поле '{field_name}' должно быть числом или null.")
    num = float(value)
    if num < 0:
        raise ModelLayersError(f"Поле '{field_name}' не может быть отрицательным.")
    return num


@dataclass(frozen=True)
class ModelLayer:
    """Слой модели (пока только LoRA/адаптер Ollama)."""

    id: str
    kind: str = LAYER_KIND_OLLAMA_ADAPTER
    description: str = ""
    size_gb: Optional[float] = None
    created_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "description": self.description,
            "created_at": self.created_at,
        }
        if self.size_gb is not None:
            payload["size_gb"] = self.size_gb
        return payload

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ModelLayer":
        if not isinstance(data, dict):
            raise ModelLayersError("Ожидался объект слоя (dict).")

        layer_id = _as_non_empty_str(data.get("id"), field_name="id")
        kind = _as_non_empty_str(data.get("kind", LAYER_KIND_OLLAMA_ADAPTER), field_name="kind")
        description_raw = data.get("description", "")
        description = description_raw if isinstance(description_raw, str) else str(description_raw)
        size_gb = _as_optional_float(data.get("size_gb"), field_name="size_gb")
        created_at = _as_optional_str(data.get("created_at"), field_name="created_at") or _utc_now_iso()

        return ModelLayer(
            id=layer_id,
            kind=kind,
            description=description,
            size_gb=size_gb,
            created_at=created_at,
        )


@dataclass
class ModelLayersForModel:
    active_layer_id: Optional[str] = None
    layers: List[ModelLayer] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_layer_id": self.active_layer_id,
            "layers": [layer.to_dict() for layer in self.layers],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ModelLayersForModel":
        if not isinstance(data, dict):
            raise ModelLayersError("Ожидался объект модели (dict).")

        active_layer_id = _as_optional_str(data.get("active_layer_id"), field_name="active_layer_id")
        layers_raw = data.get("layers", [])
        if not isinstance(layers_raw, list):
            raise ModelLayersError("Поле 'layers' должно быть списком.")

        layers = [ModelLayer.from_dict(item) for item in layers_raw]
        return ModelLayersForModel(active_layer_id=active_layer_id, layers=layers)

    def find_layer(self, layer_id: str) -> Optional[ModelLayer]:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None


@dataclass
class ModelLayersConfig:
    version: int = CONFIG_VERSION
    models: Dict[str, ModelLayersForModel] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "models": {name: entry.to_dict() for name, entry in self.models.items()},
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ModelLayersConfig":
        if not isinstance(data, dict):
            raise ModelLayersError("Ожидался JSON-объект конфигурации (dict).")

        version = data.get("version", CONFIG_VERSION)
        if version != CONFIG_VERSION:
            raise ModelLayersError(
                f"Неподдерживаемая версия model_layers.json: {version} (ожидалась {CONFIG_VERSION})."
            )

        models_raw = data.get("models", {})
        if not isinstance(models_raw, dict):
            raise ModelLayersError("Поле 'models' должно быть объектом (dict).")

        models: Dict[str, ModelLayersForModel] = {}
        for model_name, entry_raw in models_raw.items():
            if not isinstance(model_name, str) or not model_name.strip():
                raise ModelLayersError("Ключи в 'models' должны быть непустыми строками.")
            models[model_name.strip()] = ModelLayersForModel.from_dict(entry_raw)

        return ModelLayersConfig(version=version, models=models)


class ModelLayersRegistry:
    """CRUD-реестр слоёв моделей (через JSON), с автоподхватом изменений."""

    def __init__(self, config_path: str | Path = "model_layers.json"):
        self._path = Path(config_path)
        self._config = ModelLayersConfig()
        self._last_mtime: Optional[float] = None
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> None:
        if not self._path.exists():
            self._config = ModelLayersConfig()
            self._last_mtime = None
            return

        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else {}
            self._config = ModelLayersConfig.from_dict(data)
            self._last_mtime = self._path.stat().st_mtime
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelLayersError(f"Не удалось прочитать {self._path}: {exc}") from exc

    def _reload_if_changed(self) -> None:
        if not self._path.exists():
            if self._last_mtime is not None:
                self._config = ModelLayersConfig()
                self._last_mtime = None
            return

        mtime = self._path.stat().st_mtime
        if self._last_mtime is None or mtime > self._last_mtime:
            self._load()

    def save(self) -> None:
        payload = json.dumps(self._config.to_dict(), ensure_ascii=False, indent=2)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=str(self._path.parent),
                delete=False,
                prefix=f"{self._path.name}.",
                suffix=".tmp",
            ) as tmp:
                tmp.write(payload)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name
            os.replace(temp_name, self._path)
            self._last_mtime = self._path.stat().st_mtime
        except OSError as exc:
            raise ModelLayersError(f"Не удалось сохранить {self._path}: {exc}") from exc

    def list_models(self) -> List[str]:
        self._reload_if_changed()
        return sorted(self._config.models.keys())

    def _ensure_model_entry(self, model_name: str) -> ModelLayersForModel:
        self._reload_if_changed()
        name = _as_non_empty_str(model_name, field_name="model")
        entry = self._config.models.get(name)
        if entry is None:
            entry = ModelLayersForModel()
            self._config.models[name] = entry
        return entry

    def list_layers(self, model_name: str) -> List[ModelLayer]:
        entry = self._ensure_model_entry(model_name)
        return list(entry.layers)

    def get_active_layer_id(self, model_name: str) -> Optional[str]:
        entry = self._ensure_model_entry(model_name)
        return entry.active_layer_id

    def get_active_adapter(self, model_name: str) -> Optional[str]:
        entry = self._ensure_model_entry(model_name)
        if not entry.active_layer_id:
            return None
        layer = entry.find_layer(entry.active_layer_id)
        if layer is None:
            return None
        return layer.id if layer.kind == LAYER_KIND_OLLAMA_ADAPTER else None

    def add_layer(
        self,
        model_name: str,
        layer: ModelLayer,
        *,
        activate: bool = False,
        overwrite: bool = False,
    ) -> None:
        entry = self._ensure_model_entry(model_name)
        existing_index = next((i for i, x in enumerate(entry.layers) if x.id == layer.id), None)

        if existing_index is not None and not overwrite:
            raise ModelLayersError(f"Слой '{layer.id}' уже существует у модели '{model_name}'.")

        if existing_index is not None:
            entry.layers[existing_index] = layer
        else:
            entry.layers.append(layer)

        if activate:
            entry.active_layer_id = layer.id

    def update_layer(
        self,
        model_name: str,
        layer_id: str,
        *,
        new_id: Optional[str] = None,
        kind: Optional[str] = None,
        description: Optional[str] = None,
        size_gb: Optional[float] = None,
    ) -> None:
        entry = self._ensure_model_entry(model_name)
        layer_id = _as_non_empty_str(layer_id, field_name="id")
        existing = entry.find_layer(layer_id)
        if existing is None:
            raise ModelLayersError(f"Слой '{layer_id}' не найден у модели '{model_name}'.")

        next_id = _as_non_empty_str(new_id, field_name="new_id") if new_id is not None else existing.id
        if next_id != existing.id and entry.find_layer(next_id) is not None:
            raise ModelLayersError(f"Слой '{next_id}' уже существует у модели '{model_name}'.")

        next_kind = _as_non_empty_str(kind, field_name="kind") if kind is not None else existing.kind
        next_description = description if description is not None else existing.description
        next_size_gb = size_gb if size_gb is not None else existing.size_gb

        updated = ModelLayer(
            id=next_id,
            kind=next_kind,
            description=next_description,
            size_gb=next_size_gb,
            created_at=existing.created_at,
        )

        entry.layers = [updated if x.id == layer_id else x for x in entry.layers]
        if entry.active_layer_id == layer_id:
            entry.active_layer_id = updated.id

    def remove_layer(self, model_name: str, layer_id: str) -> None:
        entry = self._ensure_model_entry(model_name)
        layer_id = _as_non_empty_str(layer_id, field_name="id")
        before = len(entry.layers)
        entry.layers = [x for x in entry.layers if x.id != layer_id]
        if len(entry.layers) == before:
            raise ModelLayersError(f"Слой '{layer_id}' не найден у модели '{model_name}'.")
        if entry.active_layer_id == layer_id:
            entry.active_layer_id = None

    def set_active_layer(self, model_name: str, layer_id: Optional[str]) -> None:
        entry = self._ensure_model_entry(model_name)
        if layer_id is None:
            entry.active_layer_id = None
            return
        layer_id = _as_non_empty_str(layer_id, field_name="id")
        if entry.find_layer(layer_id) is None:
            raise ModelLayersError(f"Слой '{layer_id}' не найден у модели '{model_name}'.")
        entry.active_layer_id = layer_id

    def dedupe(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        self._reload_if_changed()

        targets = [model_name] if model_name is not None else list(self._config.models.keys())
        removed_total = 0
        per_model: Dict[str, int] = {}

        for name in targets:
            if name is None:
                continue
            entry = self._ensure_model_entry(name)
            seen: set[str] = set()
            unique: List[ModelLayer] = []
            removed = 0
            for layer in entry.layers:
                if layer.id in seen:
                    removed += 1
                    continue
                seen.add(layer.id)
                unique.append(layer)
            entry.layers = unique
            per_model[name] = removed
            removed_total += removed

            if entry.active_layer_id and entry.find_layer(entry.active_layer_id) is None:
                entry.active_layer_id = None

        return {"removed": removed_total, "by_model": per_model}

