from __future__ import annotations

import json
import tempfile
from pathlib import Path

from model_layers import ModelLayer, ModelLayersRegistry


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected={expected!r}, actual={actual!r}")


def run_dedupe() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "model_layers.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "models": {
                        "mistral:7b-instruct": {
                            "active_layer_id": "executor-dialogue-lora",
                            "layers": [
                                {"id": "executor-dialogue-lora", "kind": "ollama_adapter"},
                                {"id": "executor-dialogue-lora", "kind": "ollama_adapter"},
                            ],
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        registry = ModelLayersRegistry(cfg_path)
        stats = registry.dedupe()
        registry.save()
        assert_equal(stats["removed"], 1, "Должен удалить 1 дубликат")
        assert_equal(len(registry.list_layers("mistral:7b-instruct")), 1, "Должен остаться 1 слой")


def run_crud() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = Path(tmp_dir) / "model_layers.json"
        registry = ModelLayersRegistry(cfg_path)

        base = "qwen2.5-coder:7b"
        registry.add_layer(base, ModelLayer(id="code-assistant-lora", description="Кодовый адаптер", size_gb=0.6), activate=True)
        registry.save()

        loaded = ModelLayersRegistry(cfg_path)
        assert_equal(loaded.get_active_adapter(base), "code-assistant-lora", "Активный адаптер должен сохраниться")
        assert_equal(len(loaded.list_layers(base)), 1, "Должен быть 1 слой")

        loaded.update_layer(base, "code-assistant-lora", description="Обновлённое описание")
        loaded.save()

        loaded2 = ModelLayersRegistry(cfg_path)
        assert_equal(loaded2.list_layers(base)[0].description, "Обновлённое описание", "Описание должно обновиться")

        raised = False
        try:
            loaded2.add_layer(base, ModelLayer(id="code-assistant-lora"))
        except Exception:
            raised = True
        assert_equal(raised, True, "Дубликат слоя должен быть запрещён по умолчанию")

        loaded2.remove_layer(base, "code-assistant-lora")
        loaded2.save()
        assert_equal(loaded2.get_active_layer_id(base), None, "После удаления активный слой должен очиститься")


if __name__ == "__main__":
    run_dedupe()
    print("OK: dedupe")
    run_crud()
    print("OK: crud")

