# Как запустить `run_nemotron.py`

1. Установите зависимости (рекомендуется venv):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-nemotron.txt
```

2. Запуск примера (укажите путь к вашей модели):

```powershell
python run_nemotron.py --model-path "F:\\Нейронки\\models\\nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q4_K_M" --prompt "Привет, Нейра!"
```

3. Советы при OOM:
- используйте `device_map="auto"` или явный `max_memory` для offload;
- уменьшите `--max-new-tokens`;
- убедитесь, что модель действительно квантизована в Q4 или совместима с bitsandbytes.

4. Интеграция в проект:
- функция `generate_with_nemotron` в `run_nemotron.py` готова для вызова из кода Neira; оберните её в адаптер с логированием и ограничениями по длине.
