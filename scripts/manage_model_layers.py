from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from model_layers import (
    LAYER_KIND_OLLAMA_ADAPTER,
    LAYER_KIND_PROFILE,
    LAYER_KIND_PROMPT,
    ModelLayer,
    ModelLayersError,
    ModelLayersRegistry,
)


def _load_prompt(prompt: str | None, prompt_file: str | None) -> str | None:
    if prompt and prompt_file:
        raise ModelLayersError("Укажите только одно из: --prompt или --prompt-file.")
    if prompt_file:
        path = Path(prompt_file)
        if not path.exists():
            raise ModelLayersError(f"Файл не найден: {path}")
        return path.read_text(encoding="utf-8")
    return prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Управление слоями моделей Neira (адаптеры, промпт-слои, профили)"
    )
    parser.add_argument(
        "--config",
        default="model_layers.json",
        help="путь к model_layers.json (по умолчанию в корне проекта)",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="показать модели и слои")

    add = sub.add_parser("add", help="добавить слой модели")
    add.add_argument("--model", required=True, help="имя базовой модели (как в Ollama)")
    add.add_argument("--id", required=True, help="id слоя (например: code-assistant-lora)")
    add.add_argument(
        "--kind",
        default=LAYER_KIND_OLLAMA_ADAPTER,
        help=f"тип слоя (например: {LAYER_KIND_OLLAMA_ADAPTER}, {LAYER_KIND_PROMPT}, {LAYER_KIND_PROFILE})",
    )
    add.add_argument("--description", default="", help="описание")
    add.add_argument("--size-gb", type=float, default=None, help="размер слоя в ГБ (опционально)")
    add.add_argument("--adapter", default=None, help="имя адаптера Ollama (если отличается от id)")
    add.add_argument("--prompt", default=None, help="системный промпт для prompt/profile слоя")
    add.add_argument("--prompt-file", default=None, help="файл с системным промптом (UTF-8)")
    add.add_argument("--activate", action="store_true", help="сделать слой активным")
    add.add_argument("--overwrite", action="store_true", help="перезаписать слой, если уже есть")

    update = sub.add_parser("update", help="обновить слой модели")
    update.add_argument("--model", required=True, help="имя базовой модели (как в Ollama)")
    update.add_argument("--id", required=True, help="id существующего слоя")
    update.add_argument("--new-id", default=None, help="переименовать слой")
    update.add_argument("--kind", default=None, help="обновить тип слоя")
    update.add_argument("--description", default=None, help="обновить описание")
    update.add_argument("--size-gb", type=float, default=None, help="обновить размер (ГБ)")
    update.add_argument("--adapter", default=None, help="обновить имя адаптера Ollama")
    update.add_argument("--prompt", default=None, help="обновить системный промпт")
    update.add_argument("--prompt-file", default=None, help="файл с системным промптом (UTF-8)")

    delete = sub.add_parser("delete", help="удалить слой модели")
    delete.add_argument("--model", required=True, help="имя базовой модели (как в Ollama)")
    delete.add_argument("--id", required=True, help="id слоя")

    activate = sub.add_parser("activate", help="сделать слой активным (или очистить)")
    activate.add_argument("--model", required=True, help="имя базовой модели (как в Ollama)")
    activate.add_argument("--id", default=None, help="id слоя (если не указан — очистить)")

    dedupe = sub.add_parser("dedupe", help="удалить дубликаты слоёв (по id)")
    dedupe.add_argument("--model", default=None, help="если указан — только для этой модели")

    return parser


def cmd_list(registry: ModelLayersRegistry) -> int:
    models = registry.list_models()
    if not models:
        print("model_layers.json пуст: слоёв нет.")
        return 0

    for name in models:
        active = registry.get_active_layer_id(name)
        print(f"\nМодель: {name}")
        print(f"  Активный слой: {active or '—'}")
        layers = registry.list_layers(name)
        if not layers:
            print("  Слои: —")
            continue
        for layer in layers:
            size = f"{layer.size_gb:.2f} ГБ" if layer.size_gb is not None else "-"
            marker = "*" if active == layer.id else " "
            desc = layer.description.strip() or "-"
            extras = []
            if layer.adapter:
                extras.append(f"adapter={layer.adapter}")
            if layer.system_prompt:
                extras.append("prompt=да")
            extra_text = f", {', '.join(extras)}" if extras else ""
            print(f"  {marker} {layer.id}  ({layer.kind}, {size}{extra_text})  {desc}")
    return 0


def cmd_add(registry: ModelLayersRegistry, args: argparse.Namespace) -> int:
    prompt = _load_prompt(args.prompt, args.prompt_file)
    layer = ModelLayer(
        id=args.id,
        kind=args.kind,
        description=args.description,
        size_gb=args.size_gb,
        adapter=args.adapter,
        system_prompt=prompt,
    )
    registry.add_layer(args.model, layer, activate=args.activate, overwrite=args.overwrite)
    registry.save()
    print(f"Готово: слой '{args.id}' добавлен к модели '{args.model}'.")
    return 0


def cmd_update(registry: ModelLayersRegistry, args: argparse.Namespace) -> int:
    prompt = _load_prompt(args.prompt, args.prompt_file)
    registry.update_layer(
        args.model,
        args.id,
        new_id=args.new_id,
        kind=args.kind,
        description=args.description,
        size_gb=args.size_gb,
        adapter=args.adapter,
        system_prompt=prompt,
    )
    registry.save()
    print(f"Готово: слой '{args.id}' обновлён у модели '{args.model}'.")
    return 0


def cmd_delete(registry: ModelLayersRegistry, args: argparse.Namespace) -> int:
    registry.remove_layer(args.model, args.id)
    registry.save()
    print(f"Готово: слой '{args.id}' удалён у модели '{args.model}'.")
    return 0


def cmd_activate(registry: ModelLayersRegistry, args: argparse.Namespace) -> int:
    registry.set_active_layer(args.model, args.id)
    registry.save()
    if args.id:
        print(f"Готово: активный слой для '{args.model}' — '{args.id}'.")
    else:
        print(f"Готово: активный слой для '{args.model}' очищен.")
    return 0


def cmd_dedupe(registry: ModelLayersRegistry, args: argparse.Namespace) -> int:
    stats = registry.dedupe(args.model)
    registry.save()
    print(f"Готово: удалено дубликатов — {stats.get('removed', 0)}.")
    return 0


def main(argv: Sequence[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        registry = ModelLayersRegistry(args.config)
        if args.cmd == "list":
            return cmd_list(registry)
        if args.cmd == "add":
            return cmd_add(registry, args)
        if args.cmd == "update":
            return cmd_update(registry, args)
        if args.cmd == "delete":
            return cmd_delete(registry, args)
        if args.cmd == "activate":
            return cmd_activate(registry, args)
        if args.cmd == "dedupe":
            return cmd_dedupe(registry, args)
        raise AssertionError(f"Неизвестная команда: {args.cmd}")
    except ModelLayersError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
