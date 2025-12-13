"""Установка моделей для Neira через Ollama.

Скрипт подтягивает обязательные модели и опционально neira-personality.
Использует `ollama pull` и выводит понятные сообщения об ошибках.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable, List, Sequence

OLLAMA_API_URL = "http://localhost:11434/api/version"


@dataclass(frozen=True)
class ModelSpec:
    """Описание модели для загрузки."""

    name: str
    reason: str


REQUIRED_MODELS: List[ModelSpec] = [
    ModelSpec(name="qwen2.5-coder:7b", reason="модель для кода"),
    ModelSpec(name="mistral:7b-instruct", reason="модель для рассуждений"),
    ModelSpec(name="nomic-embed-text", reason="embedding-модель для поиска"),
]

PERSONALITY_MODEL = ModelSpec(
    name="neira-personality", reason="диалоговая модель с личностью"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Скачать модели Ollama, используемые Neira"
    )
    parser.add_argument(
        "--with-personality",
        action="store_true",
        help="добавить загрузку neira-personality, если она уже опубликована",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="MODEL",
        help=(
            "скачать только указанные модели. Доступные: "
            "qwen2.5-coder:7b mistral:7b-instruct nomic-embed-text neira-personality"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="не выполнять команды, только показать план",
    )
    return parser


def ensure_ollama_cli() -> bool:
    if shutil.which("ollama"):
        return True
    print("❌ Команда 'ollama' не найдена в PATH. Установите Ollama и повторите.")
    return False


def warn_if_server_unavailable() -> None:
    try:
        with urllib.request.urlopen(OLLAMA_API_URL, timeout=3) as resp:
            if resp.status != 200:
                print("⚠️ Ollama отвечает нестандартно, возможно сервер не запущен.")
            return
    except urllib.error.URLError as exc:
        print(
            "⚠️ Не удалось подключиться к Ollama (http://localhost:11434). "
            "Убедитесь, что запущено 'ollama serve'. Детали:",
            exc,
        )


def pull_model(model: ModelSpec, dry_run: bool) -> bool:
    command = ["ollama", "pull", model.name]
    if dry_run:
        print(f"DRY-RUN: {' '.join(command)}  # {model.reason}")
        return True

    print(f"⬇️  Скачиваю {model.name} ({model.reason})...")
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        print("❌ Команда 'ollama' не найдена. Установите Ollama и повторите.")
        return False

    if result.return_code == 0:
        print(f"✅ {model.name} готова")
        return True

    print(
        f"❌ Не удалось скачать {model.name}. Код {result.return_code}. "
        f"Stdout: {result.stdout.strip()} | Stderr: {result.stderr.strip()}"
    )
    return False


def select_models(args: argparse.Namespace) -> List[ModelSpec]:
    requested: Sequence[str] = args.only or []
    known = {spec.name: spec for spec in REQUIRED_MODELS + [PERSONALITY_MODEL]}

    if requested:
        selection = []
        for name in requested:
            if name not in known:
                print(f"⚠️ Модель {name} не известна и будет пропущена.")
                continue
            selection.append(known[name])
        return selection

    models: List[ModelSpec] = list(REQUIRED_MODELS)
    if args.with_personality:
        models.append(PERSONALITY_MODEL)
    return models


def install_models(models: Iterable[ModelSpec], dry_run: bool) -> int:
    success = True
    for spec in models:
        success &= pull_model(spec, dry_run=dry_run)
    return 0 if success else 1


def main(argv: Sequence[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    models = select_models(args)

    if not models:
        print("Нечего скачивать: список моделей пуст.")
        return 0

    if not args.dry_run:
        if not ensure_ollama_cli():
            return 1
        warn_if_server_unavailable()

    return install_models(models, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
