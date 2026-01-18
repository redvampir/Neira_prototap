"""
Запуск Harry Potter игры через WebSocket
"""
import asyncio
import json
import websockets
import sys

async def create_game():
    uri = "ws://localhost:8002/ws/chat"
    
    print("Connecting to Neira...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!\n")
            
            request = {
                "message": "Создай простую игру крестики-нолики с красивым UI",
                "use_memory": True
            }
            
            print("Request sent. Waiting for Cell Router...\n")
            await websocket.send(json.dumps(request))
            
            full_response = ""
            artifact_html = None
            
            async for message in websocket:
                if not message:
                    continue
                try:
                    data = json.loads(message)
                except:
                    print(f"\n[DEBUG] Raw message: {message[:200]}")
                    continue
                msg_type = data.get("type")
                content = data.get("content", "")
                
                print(f"\n[DEBUG] Type: {msg_type}, Content length: {len(content)}")
                
                if msg_type == "chunk":
                    print(content, end="", flush=True)
                    full_response += content
                    
                elif msg_type == "artifact":
                    print("\n\n" + "="*80)
                    print("ARTIFACT RECEIVED!")
                    print("="*80)
                    artifact_html = content
                    metadata = data.get("metadata", {})
                    artifact_info = metadata.get("artifact", {})
                    print(f"Type: {artifact_info.get('type')}")
                    print(f"Title: {artifact_info.get('title')}")
                    print(f"Size: {len(content)} bytes")
                    
                elif msg_type == "done":
                    print("\n\nDONE!")
                    break
                    
                elif msg_type == "error":
                    print(f"\nERROR: {content}")
                    return
                    
            if artifact_html:
                filename = "harry_potter_game.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(artifact_html)
                print(f"\nSaved: {filename}")
                print(f"\nOpening game in browser...")
                
                # Открываем в браузере
                import os
                os.system(f"start {filename}")
                
                print("\n" + "="*80)
                print("RESULTS:")
                print("="*80)
                if "[CELL:ui_code_cell]" in full_response:
                    print("Cell Router detected directive: YES")
                else:
                    print("Cell Router directive: NOT FOUND")
                print(f"Artifact: {len(artifact_html)} bytes")
                print("Game opened in browser")
                print("\nYou can play now!")
            else:
                print("\nWarning: No artifact generated")
                
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nMake sure backend is running:")
        print("   chcp 65001")
        print("   python -c \"import uvicorn; uvicorn.run('backend.api:app', host='0.0.0.0', port=8002)\"")

if __name__ == "__main__":
    asyncio.run(create_game())
