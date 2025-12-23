"""Простой WebSocket клиент для тестирования без импорта backend модулей."""
import asyncio
import json
import websockets
import webbrowser
from pathlib import Path


async def test_tictactoe():
    """Попросить Neira создать игру TicTacToe."""
    uri = "ws://localhost:8001/ws/chat"
    
    try:
        async with websockets.connect(uri) as ws:
            # Отправляем запрос
            request = {
                "message": "Создай интерфейс для игры в крестики-нолики 3x3",
                "context": {}
            }
            
            await ws.send(json.dumps(request))
            print(f"📤 Запрос отправлен")
            
            # Получаем ответы
            artifact_id = None
            
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    data = json.loads(msg)
                    
                    print(f"📥 Получено: {data.get('type')}")
                    
                    if data.get('type') == 'artifact':
                        artifact = data.get('metadata', {}).get('artifact')
                        if artifact:
                            artifact_id = artifact['id']
                            print(f"✅ Артефакт создан: {artifact_id}")
                            print(f"   Template: {artifact.get('template_used')}")
                            
                            # Открываем в браузере
                            html_path = Path(f"artifacts/{artifact_id}.html")
                            if html_path.exists():
                                webbrowser.open(str(html_path.absolute()))
                                print(f"🌐 Открыто в браузере")
                    
                    elif data.get('type') == 'done':
                        print("✅ Завершено")
                        break
                        
                except asyncio.TimeoutError:
                    print("⏱️ Timeout")
                    break
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
                    break
            
            if artifact_id:
                print(f"\n🎮 Артефакт: artifacts/{artifact_id}.html")
            else:
                print("\n❌ Артефакт не создан")
                
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")


if __name__ == "__main__":
    print("🧪 Тест: Создание TicTacToe UI\n")
    asyncio.run(test_tictactoe())
