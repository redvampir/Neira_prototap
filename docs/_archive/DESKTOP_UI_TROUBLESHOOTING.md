# Desktop UI — Диагностика и устранение проблем

## Проблема: "Disconnected" в правом верхнем углу

### Быстрая проверка
```powershell
# 1. Проверь, что backend запущен
$conn = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
if ($conn) { "✅ Backend слушает 8001" } else { "❌ Backend НЕ запущен" }

# 2. Проверь REST API
Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/health' -Method Get | ConvertTo-Json -Depth 2

# 3. Проверь WebSocket (через браузер F12 Console)
# ws = new WebSocket('ws://127.0.0.1:8001/ws/chat')
# ws.onopen = () => console.log('connected')
# ws.onerror = (e) => console.error(e)
```

### Быстрое решение
```powershell
# Перезапуск Desktop UI одной командой
./restart_desktop_8001.ps1
```

---

## Возможные причины и решения

### 1. Backend не запущен
**Симптомы**: "Disconnected", никаких запросов в консоли браузера  
**Решение**:
```powershell
uvicorn backend.api:app --host 127.0.0.1 --port 8001
```

### 2. Неправильный порт во фронтенде
**Симптомы**: подключается к 8000, а backend на 8001  
**Решение**: используй `frontend/index_8001.html` (он уже настроен на 8001)

### 3. Ошибка при обработке запроса
**Симптомы**: соединение устанавливается, но разрывается после отправки сообщения  
**Решение**: смотри логи backend в терминале, найди traceback

### 4. Timeout соединения
**Симптомы**: "Disconnected" через 30-60 секунд простоя  
**Решение**: теперь добавлен keepalive (ping каждые 30 сек), должно работать стабильнее

### 5. CORS проблемы
**Симптомы**: ошибки в консоли браузера про CORS  
**Решение**: уже настроено `allow_origins=["*"]` в backend

### 6. Ollama не запущен
**Симптомы**: соединение есть, но ошибка "model not found" при ответе  
**Решение**:
```powershell
# Проверь Ollama
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -Method Get
```

---

## Логи и отладка

### Включить подробные логи backend
```powershell
uvicorn backend.api:app --host 127.0.0.1 --port 8001 --log-level debug
```

### Посмотреть логи WebSocket в браузере
1. Открой F12 (DevTools)
2. Вкладка Console
3. Фильтр: `WebSocket`

### Посмотреть Network traffic
1. F12 → Network → WS (WebSocket)
2. Видно все сообщения туда-обратно

---

## Улучшения v0.6.1 (текущая версия)

✅ **Keepalive**: ping каждые 30 секунд для поддержания соединения  
✅ **Увеличенный reconnect**: до 20 попыток (было 5)  
✅ **Exponential backoff**: задержка между попытками 1.5x (макс 10 сек)  
✅ **Лучшая обработка ошибок**: детальные логи в backend  
✅ **Timeout защита**: receive с timeout 1 сек, не блокирует ping  

---

## Если ничего не помогло

1. **Перезагрузи браузер** (Ctrl+Shift+R для hard refresh)
2. **Перезапусти backend**: `./restart_desktop_8001.ps1`
3. **Проверь firewall**: возможно блокирует WebSocket
4. **Попробуй другой браузер**: Chrome/Firefox/Edge

Если всё ещё не работает — скопируй ошибку из консоли браузера (F12) и логи backend.
