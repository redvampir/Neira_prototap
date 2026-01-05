"""
Model Manager v0.6 - управление VRAM, переключение моделей и поддержка слоёв (адаптеров)

Слой (layer) — это LoRA/адаптер Ollama, подключаемый через `options.adapter`.
Управление слоями: `manage_model_layers.py` и `model_layers.json`.
"""

import requests
import time
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass

OLLAMA_API = "http://localhost:11434/api"


@dataclass
class ModelInfo:
    """Model metadata"""
    name: str
    size_gb: float
    type: str  # local / cloud
    use_case: str


# Model registry
MODELS = {
    # Локальные модели
    "code": ModelInfo("nemotron-mini", 6.0, "local", "Universal base (code tasks)"),
    "reason": ModelInfo("nemotron-mini", 6.0, "local", "Universal base (reasoning)"),
    "personality": ModelInfo("nemotron-mini", 6.0, "local", "Universal base (dialogue)"),

    # Облачные модели (0 VRAM, удалённые вычисления)
    "cloud_code": ModelInfo("qwen3-coder:480b-cloud", 0, "cloud", "Complex code tasks (480B params)"),
    "cloud_universal": ModelInfo("deepseek-v3.1:671b-cloud", 0, "cloud", "Complex universal tasks (671B params)"),
    "cloud_vision": ModelInfo("qwen3-vl:235b-cloud", 0, "cloud", "Multimodal tasks (235B params)")
}


class ModelManager:
    """Manages model loading/unloading to stay within VRAM limits"""

    def __init__(self, max_vram_gb: float = 8.0, verbose: bool = True, layers_config_path: str = "model_layers.json"):
        self.max_vram = max_vram_gb
        self.current_model: Optional[str] = None
        self.switch_count = 0
        self.verbose = verbose
        self.cloud_models_available = self._check_cloud_models()

        self._layers_registry = None
        try:
            from model_layers import ModelLayersRegistry

            self._layers_registry = ModelLayersRegistry(layers_config_path)
        except Exception as e:
            self.log(f"⚠️ Слои моделей отключены: {e}")

    def log(self, message: str):
        if self.verbose:
            print(message)

    def _check_cloud_models(self) -> Dict[str, bool]:
        """Check which cloud models are available in Ollama"""
        available = {
            "cloud_code": False,
            "cloud_universal": False,
            "cloud_vision": False
        }
        try:
            resp = requests.get(f"{OLLAMA_API}/tags", timeout=5)
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]

            for key in ["cloud_code", "cloud_universal", "cloud_vision"]:
                cloud_model = MODELS[key].name
                available[key] = cloud_model in model_names or any(cloud_model in m for m in model_names)

        except Exception as e:
            self.log(f"⚠️ Failed to check cloud models: {e}")

        return available

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

    def preload_model(self, model_name: str) -> bool:
        """Preload model into VRAM (warmup)"""
        try:
            self.log(f"🔄 Loading: {model_name}...")
            start = time.time()

            payload: Dict[str, Any] = {
                "model": model_name,
                "prompt": "init",
                "stream": False,
                "keep_alive": "10m",
            }

            if self._layers_registry is not None:
                adapter = self._layers_registry.get_active_adapter(model_name)
                if adapter:
                    payload["options"] = {"adapter": adapter}

            resp = requests.post(
                f"{OLLAMA_API}/generate",
                json=payload,
                timeout=60,
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
            if not self.cloud_models_available.get(target_key, False):
                self.log(f"⚠️ Cloud model '{target_key}' not available in Ollama")
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
        current_info = MODELS.get(self.current_model) if self.current_model else None
        if current_info and current_info.name == model_name and model_name in loaded:
            self.current_model = target_key
            return True

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
        self.switch_count += 1
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        model_info = MODELS.get(self.current_model) if self.current_model else None
        active_adapter = None
        if model_info and model_info.type == "local" and self._layers_registry is not None:
            active_adapter = self._layers_registry.get_active_adapter(model_info.name)
        return {
            "current_model": self.current_model,
            "current_model_info": model_info,
            "switches": self.switch_count,
            "loaded_models": self.get_loaded_models(),
            "cloud_models_available": self.cloud_models_available,
            "max_vram_gb": self.max_vram,
            "active_adapter": active_adapter,
        }

    def get_model_name(self, key: str) -> str:
        """Get actual model name from key"""
        if key in MODELS:
            return MODELS[key].name
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
