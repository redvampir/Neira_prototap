"""
Model Manager v0.5 — VRAM management and model switching
Manages 3 local models + 1 Ollama cloud model for complex tasks
"""

import requests
import time
import os
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

OLLAMA_API = "http://localhost:11434/api"


@dataclass
class ModelInfo:
    """Model metadata"""
    name: str
    size_gb: float
    type: str  # local / cloud
    use_case: str


@dataclass
class LoraInfo:
    """Информация о LoRA-адаптере"""

    key: str
    adapter_name: str
    size_gb: float
    base_model_key: str
    description: str = ""


@dataclass
class LoadedLoraState:
    """Состояние загруженного LoRA в VRAM"""

    info: LoraInfo
    last_used: float = field(default_factory=time.time)


class CloudModelCheckError(RuntimeError):
    """Специальная ошибка проверки доступности облачных моделей."""

    def __init__(self, message: str, *, is_network: bool = False, status_code: Optional[int] = None):
        super().__init__(message)
        self.is_network = is_network
        self.status_code = status_code


# Model registry
MODELS = {
    # Локальные модели
    "code": ModelInfo("qwen2.5-coder:7b", 5.0, "local", "Code generation and analysis"),
    "reason": ModelInfo("mistral:7b-instruct", 4.5, "local", "Planning, reasoning, verification"),
    "personality": ModelInfo("neira-personality", 1.5, "local", "Dialogue with personality"),

    # Облачные модели (0 VRAM, удалённые вычисления)
    "cloud_code": ModelInfo("qwen3-coder:480b-cloud", 0, "cloud", "Complex code tasks (480B params)"),
    "cloud_universal": ModelInfo("deepseek-v3.1:671b-cloud", 0, "cloud", "Complex universal tasks (671B params)"),
    "cloud_vision": ModelInfo("qwen3-vl:235b-cloud", 0, "cloud", "Multimodal tasks (235B params)")
}

# Реестр LoRA-адаптеров (ключ → параметры)
LORA_ADAPTERS: Dict[str, LoraInfo] = {
    "executor_dialog": LoraInfo(
        key="executor_dialog",
        adapter_name="executor-dialogue-lora",
        size_gb=0.8,
        base_model_key="reason",
        description="Диалоговая настройка исполнителя"
    ),
    "code_assistant": LoraInfo(
        key="code_assistant",
        adapter_name="code-assistant-lora",
        size_gb=0.6,
        base_model_key="code",
        description="Усиление для задач с кодом"
    )
}


class ModelManager:
    """Manages model loading/unloading to stay within VRAM limits"""

    def __init__(self, max_vram_gb: float = 8.0, verbose: bool = True):
        self.max_vram = max_vram_gb
        self.current_model: Optional[str] = None
        self.switch_count = 0
        self.verbose = verbose
        self.last_cloud_check: Optional[float] = None
        self.last_cloud_error: Optional[CloudModelCheckError] = None
        self.cloud_models_available = self._check_cloud_models()
        self.loaded_loras: Dict[str, LoadedLoraState] = {}
        self.current_vram: float = 0.0

    def log(self, message: str):
        if self.verbose:
            print(message)

    def _check_cloud_models(self) -> Dict[str, bool]:
        """Check which cloud models are available in Ollama"""
        previous_state = getattr(self, "cloud_models_available", None)
        available = previous_state.copy() if isinstance(previous_state, dict) else {
            "cloud_code": False,
            "cloud_universal": False,
            "cloud_vision": False,
        }

        attempts = 2
        last_error: Optional[Exception] = None
        self.last_cloud_error = None

        for attempt in range(1, attempts + 1):
            try:
                resp = requests.get(f"{OLLAMA_API}/tags", timeout=3)

                if resp.status_code != 200:
                    error = CloudModelCheckError(
                        "⚠️ Ollama /tags вернул ошибку "+
                        f"{resp.status_code}: тело='{resp.text}', заголовки={dict(resp.headers)}",
                        status_code=resp.status_code,
                    )
                    self.last_cloud_error = error
                    self.log(str(error))
                    self.last_cloud_check = time.time()
                    return {key: False for key in available}

                try:
                    models = resp.json().get("models", [])
                except Exception as json_error:
                    body_snippet = resp.text[:500]
                    error = CloudModelCheckError(
                        "⚠️ Ошибка разбора JSON /tags: "
                        f"{json_error}; тело='{body_snippet}', заголовки={dict(resp.headers)}",
                        status_code=resp.status_code,
                    )
                    self.last_cloud_error = error
                    self.log(str(error))
                    self.last_cloud_check = time.time()
                    return available

                model_names = [m.get("name", "") for m in models]

                for key in ["cloud_code", "cloud_universal", "cloud_vision"]:
                    cloud_model = MODELS[key].name
                    available[key] = cloud_model in model_names or any(cloud_model in m for m in model_names)

                self.last_cloud_check = time.time()
                self.last_cloud_error = None
                return available

            except requests.RequestException as exc:
                last_error = exc
                error = CloudModelCheckError(
                    f"⚠️ Сетевая ошибка при проверке облачных моделей (попытка {attempt}/{attempts}): {exc}",
                    is_network=True,
                )
                self.last_cloud_error = error
                self.log(str(error))
                if attempt < attempts:
                    time.sleep(0.5)
                continue
            except Exception as exc:
                last_error = exc
                error = CloudModelCheckError(
                    f"⚠️ Неожиданная ошибка при проверке облачных моделей: {exc}"
                )
                self.last_cloud_error = error
                self.log(str(error))
                self.last_cloud_check = time.time()
                return available

        if last_error:
            error = CloudModelCheckError(
                f"⚠️ Не удалось проверить облачные модели: {last_error}",
                is_network=isinstance(last_error, requests.RequestException),
            )
            self.last_cloud_error = error
            self.log(str(error))
        self.last_cloud_check = time.time()
        return available

    def refresh_cloud_models(self, *, force: bool = False) -> Dict[str, bool]:
        """Обновить состояние доступности облачных моделей с троттлингом."""
        if self.last_cloud_check and not force:
            elapsed = time.time() - self.last_cloud_check
            if elapsed < 30:
                return self.cloud_models_available

        self.cloud_models_available = self._check_cloud_models()
        return self.cloud_models_available

    def get_cloud_status(self) -> Tuple[Dict[str, bool], Optional[CloudModelCheckError]]:
        """Получить флаги доступности и последнюю ошибку проверки."""
        return self.cloud_models_available, self.last_cloud_error

    def _current_base_vram(self) -> float:
        """Оценка VRAM, занимаемой базовой моделью."""
        if self.current_model and MODELS.get(self.current_model):
            model_info = MODELS[self.current_model]
            if model_info.type == "local":
                return model_info.size_gb
        return 0.0

    def _update_vram_usage(self):
        lora_sum = sum(state.info.size_gb for state in self.loaded_loras.values())
        self.current_vram = self._current_base_vram() + lora_sum

    def _evict_incompatible_loras(self):
        """Выгрузить LoRA, несовместимые с текущей базовой моделью."""
        incompatible = [
            key for key, state in self.loaded_loras.items()
            if state.info.base_model_key != self.current_model
        ]
        for key in incompatible:
            self.unload_lora(key)

    def get_loaded_models(self) -> list:
        """Check which models are currently in VRAM"""
        try:
            resp = requests.get(f"{OLLAMA_API}/ps", timeout=5)
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            self.log(f"⚠️ Failed to check loaded models: {e}")
            return []

    def unload_model(self, model_name: str):
        """Unload model from VRAM"""
        try:
            # Ollama automatically unloads when keep_alive=0
            requests.post(
                f"{OLLAMA_API}/generate",
                json={"model": model_name, "keep_alive": 0},
                timeout=10
            )
            self.log(f"🗑️ Unloaded: {model_name}")
        except Exception as e:
            self.log(f"⚠️ Failed to unload {model_name}: {e}")

    def _load_lora_via_api(self, adapter_name: str, keep_alive: str = "10m") -> bool:
        """Загрузить LoRA через API Ollama/llama.cpp"""
        base_model = self.get_model_name(self.current_model or "")
        if not base_model:
            self.log("⚠️ Не выбрана базовая модель для загрузки LoRA")
            return False
        try:
            resp = requests.post(
                f"{OLLAMA_API}/generate",
                json={
                    "model": base_model,
                    "prompt": "init",
                    "stream": False,
                    "keep_alive": keep_alive,
                    "options": {"adapter": adapter_name},
                },
                timeout=60,
            )
            if resp.status_code == 200:
                return True
            self.log(f"❌ Не удалось загрузить LoRA {adapter_name}: {resp.status_code}")
        except Exception as exc:
            self.log(f"❌ Ошибка при загрузке LoRA {adapter_name}: {exc}")
        return False

    def _unload_lora_via_api(self, adapter_name: str):
        base_model = self.get_model_name(self.current_model or "")
        if not base_model:
            return
        try:
            requests.post(
                f"{OLLAMA_API}/generate",
                json={
                    "model": base_model,
                    "prompt": "cleanup",
                    "stream": False,
                    "keep_alive": 0,
                    "options": {"adapter": adapter_name},
                },
                timeout=30,
            )
        except Exception as exc:
            self.log(f"⚠️ Ошибка выгрузки LoRA {adapter_name}: {exc}")

    def preload_model(self, model_name: str) -> bool:
        """Preload model into VRAM (warmup)"""
        try:
            self.log(f"🔄 Loading: {model_name}...")
            start = time.time()

            resp = requests.post(
                f"{OLLAMA_API}/generate",
                json={
                    "model": model_name,
                    "prompt": "init",
                    "stream": False,
                    "keep_alive": "10m"
                },
                timeout=60
            )

            if resp.status_code == 200:
                elapsed = time.time() - start
                self.log(f"✅ Loaded in {elapsed:.1f}s")
                return True
            else:
                self.log(f"❌ Load failed: {resp.status_code}")
                return False

        except Exception as e:
            self.log(f"❌ Load error: {e}")
            return False

    def can_load_lora(self, adapter_key: str) -> bool:
        """Проверить, можно ли загрузить LoRA с учётом VRAM и LRU-выгрузки."""
        if adapter_key not in LORA_ADAPTERS:
            self.log(f"❌ Неизвестный LoRA-ключ: {adapter_key}")
            return False

        if self.current_model is None:
            self.log("⚠️ Сначала выбери базовую модель перед загрузкой LoRA")
            return False

        if MODELS.get(self.current_model, ModelInfo("", 0, "cloud", "")).type != "local":
            self.log("⚠️ LoRA доступна только для локальных моделей")
            return False

        info = LORA_ADAPTERS[adapter_key]
        if info.base_model_key != self.current_model:
            self.log(f"⚠️ LoRA {adapter_key} рассчитана на {info.base_model_key}, а активна {self.current_model}")
            return False

        if adapter_key in self.loaded_loras:
            self.loaded_loras[adapter_key].last_used = time.time()
            return True

        projected = self._current_base_vram() + sum(s.info.size_gb for s in self.loaded_loras.values()) + info.size_gb
        while projected > self.max_vram and self.loaded_loras:
            # LRU: выгружаем самый давно использованный адаптер
            lru_key = min(self.loaded_loras.items(), key=lambda item: item[1].last_used)[0]
            if lru_key == adapter_key:
                break
            self.unload_lora(lru_key)
            projected = self._current_base_vram() + sum(s.info.size_gb for s in self.loaded_loras.values()) + info.size_gb

        if projected > self.max_vram:
            self.log(
                f"❌ Недостаточно VRAM для LoRA {adapter_key}: нужно {projected:.1f}ГБ, доступно {self.max_vram:.1f}ГБ"
            )
            return False
        return True

    def load_lora(self, adapter_key: str) -> bool:
        """Загрузить LoRA с учётом VRAM и LRU."""
        if adapter_key not in LORA_ADAPTERS:
            self.log(f"❌ Неизвестный LoRA-адаптер: {adapter_key}")
            return False

        info = LORA_ADAPTERS[adapter_key]
        if info.base_model_key and self.current_model != info.base_model_key:
            if not self.switch_to(info.base_model_key):
                return False

        if not self.can_load_lora(adapter_key):
            return False

        if adapter_key in self.loaded_loras:
            self.loaded_loras[adapter_key].last_used = time.time()
            return True

        if self._load_lora_via_api(info.adapter_name):
            self.loaded_loras[adapter_key] = LoadedLoraState(info=info)
            self._update_vram_usage()
            self.log(f"✨ LoRA загружена: {info.adapter_name} (VRAM {info.size_gb} ГБ)")
            return True
        return False

    def unload_lora(self, adapter_key: str):
        if adapter_key not in self.loaded_loras:
            return
        info = self.loaded_loras[adapter_key].info
        self._unload_lora_via_api(info.adapter_name)
        del self.loaded_loras[adapter_key]
        self._update_vram_usage()
        self.log(f"🗑️ Выгружен LoRA: {info.adapter_name}")

    def switch_to(self, target_key: str) -> bool:
        """
        Switch to target model, managing VRAM

        Args:
            target_key: "code" / "reason" / "personality" / "cloud"

        Returns:
            True if successfully switched
        """
        if target_key not in MODELS:
            self.log(f"❌ Unknown model key: {target_key}")
            return False

        model_info = MODELS[target_key]

        # Cloud model - also managed by Ollama, but no VRAM constraints
        if model_info.type == "cloud":
            self.refresh_cloud_models()
            if not self.cloud_models_available.get(target_key, False):
                reason = f" Причина: {self.last_cloud_error}" if self.last_cloud_error else ""
                self.log(f"⚠️ Cloud model '{target_key}' not available in Ollama.{reason}")
                return False
            # Don't unload local models for cloud - it uses remote compute
            self.current_model = target_key
            self.log(f"🌩️ Using cloud model: {model_info.name}")
            return True

        # Local model - check if already loaded
        model_name = model_info.name
        if self.current_model == target_key:
            return True

        loaded = self.get_loaded_models()

        # Unload other models if needed
        for model in loaded:
            if model != model_name:
                self.unload_model(model)
                time.sleep(0.5)  # Give Ollama time to cleanup

        # Load target model if not already loaded
        if model_name not in loaded:
            success = self.preload_model(model_name)
            if not success:
                return False

        self.current_model = target_key
        self._evict_incompatible_loras()
        self._update_vram_usage()
        self.switch_count += 1
        return True

    def activate_lora_for_cell(self, cell_name: str, adapter_key: Optional[str]) -> None:
        """Загрузить LoRA при переключении на клетку."""
        if not adapter_key:
            return
        if self.load_lora(adapter_key):
            self.log(f"🔌 Клетка {cell_name} активировала LoRA {adapter_key}")

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        self._update_vram_usage()
        return {
            "current_model": self.current_model,
            "current_model_info": MODELS.get(self.current_model),
            "switches": self.switch_count,
            "loaded_models": self.get_loaded_models(),
            "cloud_models_available": self.cloud_models_available,
            "max_vram_gb": self.max_vram,
            "current_vram_gb": round(self.current_vram, 2),
            "loaded_loras": [state.info.adapter_name for state in self.loaded_loras.values()],
            "lora_registry": {k: v.adapter_name for k, v in LORA_ADAPTERS.items()}
        }

    def get_model_name(self, key: str) -> str:
        """Get actual model name from key"""
        if key in MODELS:
            return MODELS[key].name
        return ""

    def get_adapter_name(self, adapter_key: str) -> str:
        if adapter_key in LORA_ADAPTERS:
            return LORA_ADAPTERS[adapter_key].adapter_name
        return ""


# === TEST ===
if __name__ == "__main__":
    print("Model Manager Test")
    print("=" * 50)

    manager = ModelManager(verbose=True)

    print("\n1. Testing model switch to reason (mistral)...")
    manager.switch_to("reason")

    print("\n2. Stats:")
    stats = manager.get_stats()
    for key, val in stats.items():
        print(f"  {key}: {val}")

    print("\n3. Testing model switch to code (qwen-coder)...")
    manager.switch_to("code")

    print("\n4. Final stats:")
    stats = manager.get_stats()
    print(f"  Current: {stats['current_model']}")
    print(f"  Switches: {stats['switches']}")
    print(f"  Loaded: {stats['loaded_models']}")
