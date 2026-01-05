"""Интерактивный тест: просим Neira создать UI для крестиков-ноликов."""
import asyncio
import json
import websockets
import webbrowser
import os
from pathlib import Path


async def chat_with_neira(message: str) -> dict:
    """Отправить сообщение Neira через WebSocket."""
    uri = "ws://localhost:8001/ws/chat"
    
    async with websockets.connect(uri) as websocket:
        # Отправить сообщение
        await websocket.send(json.dumps({
            "message": message,
            "context": {}
        }))
        
        print(f"📤 Отправлено: {message}")
        print("⏳ Жду ответа от Neira...\n")
        
        # Получить все ответы (streaming)
        responses = []
        artifact_data = None
        
        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(response)
                responses.append(data)
                
                print(f"📦 Получено: type={data.get('type')}")
                
                # Если это artifact, сохраняем
                if data.get('type') == 'artifact':
                    artifact_data = data
                
                # Если это финальный ответ (type=complete или message)
                if data.get('type') in ['complete', 'message']:
                    break
                    
        except asyncio.TimeoutError:
            print("⏱️ Timeout — завершаю получение")
        
        # Вернуть artifact или последний ответ
        return artifact_data if artifact_data else (responses[-1] if responses else {})


async def main():
    print("=" * 60)
    print("🎮 ТЕСТ: Neira создаёт UI для крестиков-ноликов")
    print("=" * 60)
    print()
    
    # Шаг 1: Попросить Neira создать UI
    print("📝 Шаг 1: Запрашиваю создание интерфейса")
    print("-" * 60)
    
    request = "Создай интерфейс для игры в крестики-нолики с кнопками 3x3"
    
    try:
        response = await chat_with_neira(request)
        
        print("✅ Ответ получен!")
        print(f"Type: {response.get('type')}")
        
        # Debug: показать полный ответ
        print("\n🔍 DEBUG: Полный ответ:")
        print(json.dumps(response, ensure_ascii=False, indent=2)[:500])
        print()
        
        # Проверить, создан ли artifact
        if response.get('type') == 'artifact':
            # Попробовать разные пути к данным
            artifact = (response.get('metadata', {}).get('artifact') or 
                       response.get('artifact') or 
                       response.get('data', {}))
            
            artifact_id = artifact.get('id')
            template = artifact.get('template_used')
            
            print()
            print("🎨 Artifact создан!")
            print(f"   ID: {artifact_id}")
            print(f"   Template: {template}")
            print()
            
            # Шаг 2: Открыть HTML файл
            html_path = Path(f"artifacts/{artifact_id}.html")
            
            if html_path.exists():
                print(f"📂 Файл найден: {html_path}")
                print("🌐 Открываю в браузере...")
                
                # Открыть в браузере
                abs_path = html_path.absolute()
                webbrowser.open(f"file:///{abs_path}")
                
                print()
                print("=" * 60)
                print("✅ УСПЕХ! UI открыт в браузере")
                print("=" * 60)
                print()
                print("🎮 Можешь играть!")
                print()
                print("📊 Статистика:")
                print(f"   - Artifact ID: {artifact_id}")
                print(f"   - HTML размер: {html_path.stat().st_size} байт")
                print(f"   - Путь: {abs_path}")
                
            else:
                print(f"❌ Файл не найден: {html_path}")
                print("Проверяю JSON...")
                
                json_path = Path(f"artifacts/{artifact_id}.json")
                if json_path.exists():
                    print(f"✅ JSON найден: {json_path}")
                    with open(json_path, 'r', encoding='utf-8') as f:
                        artifact_data = json.load(f)
                    
                    # Создать HTML вручную
                    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Neira Artifact: {artifact_id}</title>
    <style>{artifact_data.get('css', '')}</style>
</head>
<body>
    {artifact_data.get('html', '')}
    <script>{artifact_data.get('js', '')}</script>
</body>
</html>"""
                    
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    
                    print(f"✅ HTML создан вручную: {html_path}")
                    webbrowser.open(f"file:///{html_path.absolute()}")
        
        elif 'error' in response:
            print(f"❌ Ошибка: {response['error']}")
        
        else:
            print("⚠️ Artifact не создан")
            print(f"Полный ответ: {json.dumps(response, ensure_ascii=False, indent=2)}")
    
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print()
        print("Убедись, что backend запущен:")
        print("  python -m backend.api")


if __name__ == "__main__":
    asyncio.run(main())
