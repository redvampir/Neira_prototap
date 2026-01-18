from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"
DEFAULT_DATASET = "training_data/hitl_russian_training.jsonl"
DEFAULT_OUTPUT_DIR = "artifacts/lora_adapter"
DEFAULT_MERGED_DIR = "artifacts/lora_merged"
DEFAULT_GGUF_PATH = "artifacts/neira-russian-hitl.gguf"
DEFAULT_OLLAMA_MODEL = "neira-russian-hitl-lora:latest"

DEFAULT_MAX_SEQ_LEN = 1024
DEFAULT_EPOCHS = 3
DEFAULT_BATCH_SIZE = 1
DEFAULT_GRAD_ACCUM = 8
DEFAULT_LEARNING_RATE = 2e-4
DEFAULT_SEED = 42

DEFAULT_LORA_R = 16
DEFAULT_LORA_ALPHA = 32
DEFAULT_LORA_DROPOUT = 0.05
DEFAULT_TARGET_MODULES = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
)

MIN_VALIDATION_SAMPLES = 20
VALIDATION_SPLIT = 0.05


@dataclass(frozen=True)
class TrainConfig:
    """Параметры обучения LoRA."""

    base_model: str
    dataset_path: Path
    output_dir: Path
    merged_dir: Path
    gguf_path: Path
    ollama_model: str
    llama_cpp_dir: Optional[Path]
    prompt_field: str
    completion_field: str
    max_seq_len: int
    epochs: int
    batch_size: int
    grad_accum: int
    learning_rate: float
    seed: int
    lora_r: int
    lora_alpha: int
    lora_dropout: float
    target_modules: List[str]
    use_4bit: bool
    fp16: bool
    bf16: bool


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LoRA-пайплайн: обучение, merge, GGUF, Ollama create."
    )
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL, help="HF базовая модель.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="JSONL с prompt/completion.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Каталог адаптера.")
    parser.add_argument("--merged-dir", default=DEFAULT_MERGED_DIR, help="Каталог merged модели.")
    parser.add_argument("--gguf-path", default=DEFAULT_GGUF_PATH, help="Путь GGUF результата.")
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL, help="Имя модели в Ollama.")
    parser.add_argument("--llama-cpp-dir", default="", help="Путь к llama.cpp (для конвертации).")
    parser.add_argument("--prompt-field", default="prompt", help="Поле prompt в JSONL.")
    parser.add_argument("--completion-field", default="completion", help="Поле completion в JSONL.")
    parser.add_argument("--max-seq-len", type=int, default=DEFAULT_MAX_SEQ_LEN)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--grad-accum", type=int, default=DEFAULT_GRAD_ACCUM)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--lora-r", type=int, default=DEFAULT_LORA_R)
    parser.add_argument("--lora-alpha", type=int, default=DEFAULT_LORA_ALPHA)
    parser.add_argument("--lora-dropout", type=float, default=DEFAULT_LORA_DROPOUT)
    parser.add_argument(
        "--target-modules",
        default=",".join(DEFAULT_TARGET_MODULES),
        help="Список модулей через запятую.",
    )
    parser.add_argument("--use-4bit", action="store_true", help="Загрузка в 4-bit.")
    parser.add_argument("--fp16", action="store_true", help="FP16 обучение.")
    parser.add_argument("--bf16", action="store_true", help="BF16 обучение.")
    return parser


def _parse_args() -> TrainConfig:
    args = _build_parser().parse_args()
    target_modules = [item.strip() for item in args.target_modules.split(",") if item.strip()]
    llama_cpp_dir = Path(args.llama_cpp_dir).expanduser() if args.llama_cpp_dir else None
    return TrainConfig(
        base_model=str(args.base_model).strip(),
        dataset_path=Path(args.dataset).expanduser(),
        output_dir=Path(args.output_dir).expanduser(),
        merged_dir=Path(args.merged_dir).expanduser(),
        gguf_path=Path(args.gguf_path).expanduser(),
        ollama_model=str(args.ollama_model).strip(),
        llama_cpp_dir=llama_cpp_dir,
        prompt_field=str(args.prompt_field).strip(),
        completion_field=str(args.completion_field).strip(),
        max_seq_len=int(args.max_seq_len),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        grad_accum=int(args.grad_accum),
        learning_rate=float(args.learning_rate),
        seed=int(args.seed),
        lora_r=int(args.lora_r),
        lora_alpha=int(args.lora_alpha),
        lora_dropout=float(args.lora_dropout),
        target_modules=target_modules,
        use_4bit=bool(args.use_4bit),
        fp16=bool(args.fp16),
        bf16=bool(args.bf16),
    )


def _ensure_dirs(config: TrainConfig) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.merged_dir.mkdir(parents=True, exist_ok=True)
    config.gguf_path.parent.mkdir(parents=True, exist_ok=True)


def _load_dataset(path: Path) -> Any:
    from datasets import load_dataset

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return load_dataset("json", data_files=str(path), split="train")


def _format_text(prompt: str, completion: str, tokenizer: Any) -> str:
    prompt = prompt.strip()
    completion = completion.strip()
    if not prompt or not completion:
        return ""
    if getattr(tokenizer, "chat_template", None):
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": completion},
        ]
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
    return f"User: {prompt}\nAssistant: {completion}"


def _prepare_dataset(dataset: Any, config: TrainConfig, tokenizer: Any) -> Any:
    prompt_key = config.prompt_field
    completion_key = config.completion_field

    def _map_row(row: Dict[str, Any]) -> Dict[str, str]:
        text = _format_text(
            str(row.get(prompt_key, "")),
            str(row.get(completion_key, "")),
            tokenizer,
        )
        return {"text": text}

    dataset = dataset.map(_map_row, remove_columns=list(dataset.column_names))
    dataset = dataset.filter(lambda row: bool(row.get("text", "").strip()))
    return dataset


def _train_eval_split(dataset: Any, seed: int) -> tuple[Any, Optional[Any]]:
    total = int(getattr(dataset, "num_rows", len(dataset)))
    if total < MIN_VALIDATION_SAMPLES:
        return dataset, None
    split = dataset.train_test_split(test_size=VALIDATION_SPLIT, seed=seed)
    return split["train"], split["test"]


def _load_model_and_tokenizer(config: TrainConfig) -> tuple[Any, Any]:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    load_kwargs: Dict[str, Any] = {"device_map": "auto"}
    if config.use_4bit:
        from transformers import BitsAndBytesConfig
        import torch

        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

    tokenizer = AutoTokenizer.from_pretrained(config.base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(config.base_model, **load_kwargs)
    model.config.use_cache = False
    return model, tokenizer


def _apply_lora(model: Any, config: TrainConfig) -> Any:
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    if config.use_4bit:
        model = prepare_model_for_kbit_training(model)
    lora_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=config.target_modules,
    )
    return get_peft_model(model, lora_config)


def _tokenize_dataset(dataset: Any, tokenizer: Any, config: TrainConfig) -> Any:
    def _tokenize(batch: Dict[str, List[str]]) -> Dict[str, Any]:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=config.max_seq_len,
        )

    return dataset.map(_tokenize, batched=True, remove_columns=["text"])


def _build_trainer(
    model: Any,
    tokenizer: Any,
    train_dataset: Any,
    eval_dataset: Optional[Any],
    config: TrainConfig,
) -> Any:
    from transformers import DataCollatorForLanguageModeling, TrainingArguments, Trainer

    optim = "paged_adamw_8bit" if config.use_4bit else "adamw_torch"
    eval_strategy = "steps" if eval_dataset is not None else "no"
    training_args = TrainingArguments(
        output_dir=str(config.output_dir),
        num_train_epochs=config.epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.grad_accum,
        learning_rate=config.learning_rate,
        logging_steps=10,
        save_steps=200,
        save_total_limit=1,
        evaluation_strategy=eval_strategy,
        eval_steps=200,
        fp16=config.fp16,
        bf16=config.bf16,
        report_to=[],
        seed=config.seed,
        optim=optim,
    )
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    return Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )


def _save_adapter(model: Any, tokenizer: Any, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)


def _merge_and_save(model: Any, tokenizer: Any, output_dir: Path) -> None:
    merged = model.merge_and_unload()
    output_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(output_dir, safe_serialization=True)
    tokenizer.save_pretrained(output_dir)


def _convert_to_gguf(merged_dir: Path, gguf_path: Path, llama_cpp_dir: Path) -> None:
    script_path = llama_cpp_dir / "convert_hf_to_gguf.py"
    if not script_path.exists():
        raise FileNotFoundError(f"convert_hf_to_gguf.py not found: {script_path}")
    cmd = [sys.executable, str(script_path), str(merged_dir), "--outfile", str(gguf_path)]
    subprocess.run(cmd, check=True)


def _write_modelfile(gguf_path: Path, output_dir: Path) -> Path:
    modelfile_path = output_dir / "Modelfile"
    content = f"FROM {gguf_path}\n"
    modelfile_path.write_text(content, encoding="utf-8")
    return modelfile_path


def _ollama_create(modelfile_path: Path, model_name: str) -> None:
    subprocess.run(
        ["ollama", "create", model_name, "-f", str(modelfile_path)],
        check=True,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    config = _parse_args()

    if config.fp16 and config.bf16:
        logger.error("Выберите только один режим: fp16 или bf16.")
        return 2

    try:
        _ensure_dirs(config)
        dataset = _load_dataset(config.dataset_path)
        model, tokenizer = _load_model_and_tokenizer(config)
        model = _apply_lora(model, config)
        prepared = _prepare_dataset(dataset, config, tokenizer)
        train_dataset, eval_dataset = _train_eval_split(prepared, config.seed)
        train_dataset = _tokenize_dataset(train_dataset, tokenizer, config)
        if eval_dataset is not None:
            eval_dataset = _tokenize_dataset(eval_dataset, tokenizer, config)
        trainer = _build_trainer(model, tokenizer, train_dataset, eval_dataset, config)
        trainer.train()

        adapter_dir = config.output_dir / "adapter"
        _save_adapter(trainer.model, tokenizer, adapter_dir)
        _merge_and_save(trainer.model, tokenizer, config.merged_dir)

        if config.llama_cpp_dir:
            _convert_to_gguf(config.merged_dir, config.gguf_path, config.llama_cpp_dir)
            modelfile_path = _write_modelfile(config.gguf_path, config.merged_dir)
            _ollama_create(modelfile_path, config.ollama_model)
            logger.info("Ollama модель создана: %s", config.ollama_model)
        else:
            logger.warning("llama.cpp не указан, GGUF/ollama create пропущены.")

    except FileNotFoundError as exc:
        logger.error("Файл не найден: %s", exc)
        return 1
    except subprocess.CalledProcessError as exc:
        logger.error("Команда завершилась с ошибкой: %s", exc)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        logger.error("Ошибка пайплайна: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
