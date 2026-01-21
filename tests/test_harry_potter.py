"""
WebSocket тест для Harry Potter игры
Проверяет Cell Router + UICodeCell интеграцию
"""
import asyncio
import json
import websockets
import pytest


@pytest.mark.asyncio
async def test_harry_potter_game():
    """Тестируем создание Harry Potter игры через Cell Router"""
    uri = "ws://localhost:8001/ws/chat"
    
    print("🔌 Подключение к Neira WebSocket...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket подключен!")
            
            # Отправляем запрос на создание игры
            request = {
                "content": "Создай мини-игру в стиле Гарри Поттера. Нужна смесь аркады и квеста с UI, управлением клавишами и встроенным чатом для общения с Нейрой. Можно начать с простого: игрок перемещается по Хогвартсу, собирает артефакты и решает загадки.",
                "use_memory": True
            }
            
            print(f"\n📤 Отправка запроса:\n{request['content']}\n")
            await websocket.send(json.dumps(request))
            
            print("📥 Получение ответа...\n")
            print("=" * 80)
            
            full_response = ""
            artifact_found = False
            
            # Получаем streaming chunks
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "unknown")
                    content = data.get("content", "")
                    
                    if msg_type == "chunk":
                        print(content, end="", flush=True)
                        full_response += content
                        
                    elif msg_type == "artifact":
                        artifact_found = True
                        print("\n\n" + "=" * 80)
                        print("🎨 ARTIFACT RECEIVED!")
                        print("=" * 80)
                        
                        metadata = data.get("metadata", {})
                        artifact = metadata.get("artifact", {})
                        
                        print(f"Type: {artifact.get('type')}")
                        print(f"Title: {artifact.get('title')}")
                        print(f"Description: {artifact.get('description')}")
                        print(f"Size: {len(content)} bytes")
                        
                        # Сохраняем HTML
                        filename = "harry_potter_game.html"
                        with open(filename, "w", encoding="utf-8") as f:
                            f.write(content)
                        print(f"\n💾 Saved to: {filename}")
                        
                    elif msg_type == "done":
                        print("\n\n" + "=" * 80)
                        print("✅ RESPONSE COMPLETE")
                        print("=" * 80)
                        break
                        
                    elif msg_type == "error":
                        print(f"\n❌ ERROR: {content}")
                        break
                        
                except json.JSONDecodeError:
                    print(f"⚠️ Failed to parse: {message[:100]}...")
                    
            # Результаты теста
            print("\n\n" + "=" * 80)
            print("📊 TEST RESULTS")
            print("=" * 80)
            print(f"Artifact generated: {'✅ YES' if artifact_found else '❌ NO'}")
            print(f"Response length: {len(full_response)} chars")
            
            # Проверяем наличие [CELL:ui_code_cell] в ответе
            if "[CELL:ui_code_cell]" in full_response:
                print("Cell Router directive: ✅ DETECTED")
            else:
                print("Cell Router directive: ❌ NOT FOUND")
                
            if artifact_found:
                print("\n🎮 Открой harry_potter_game.html в браузере для игры!")
                
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("\n💡 Убедись что backend запущен:")
        print("   chcp 65001")
        print("   python -m backend.api")

if __name__ == "__main__":
    asyncio.run(test_harry_potter_game())
