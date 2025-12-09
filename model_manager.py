"""
Model Manager v0.5 — VRAM management and model switching
Manages 3 local models + 1 Ollama cloud model for complex tasks
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
    "code": ModelInfo("qwen2.5-coder:7b", 5.0, "local", "Code generation and analysis"),
    "reason": ModelInfo("mistral:7b-instruct", 4.5, "local", "Planning, reasoning, verification"),
    "personality": ModelInfo("neira-personality", 1.5, "local", "Dialogue with personality"),
    "cloud": ModelInfo("deepseek-v3.1:671b-cloud", 0, "cloud", "Complex tasks (Ollama cloud, 671B params)")
}


class ModelManager:
    """Manages model loading/unloading to stay within VRAM limits"""

    def __init__(self, max_vram_gb: float = 8.0, verbose: bool = True):
        self.max_vram = max_vram_gb
        self.current_model: Optional[str] = None
        self.switch_count = 0
        self.verbose = verbose
        self.cloud_available = self._check_cloud_model()

    def log(self, message: str):
        if self.verbose:
            print(message)

    def _check_cloud_model(self) -> bool:
        """Check if cloud model is available in Ollama"""
        try:
            resp = requests.get(f"{OLLAMA_API}/tags", timeout=5)
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            cloud_model = MODELS["cloud"].name
            return cloud_model in model_names or any(cloud_model in m for m in model_names)
        except:
            return False

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
            if not self.cloud_available:
                self.log("⚠️ Cloud model not available in Ollama")
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
        self.switch_count += 1
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            "current_model": self.current_model,
            "current_model_info": MODELS.get(self.current_model),
            "switches": self.switch_count,
            "loaded_models": self.get_loaded_models(),
            "cloud_available": self.cloud_available,
            "max_vram_gb": self.max_vram
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
