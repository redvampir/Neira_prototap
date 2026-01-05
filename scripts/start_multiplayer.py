"""
Скрипт для запуска multiplayer сервера с автоопределением IP
"""
import socket
import uvicorn
from multiplayer_server import app

def get_local_ip():
    """Получает локальный IP адрес компьютера"""
    try:
        # Создаём временное соединение для определения IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8003
    
    print("=" * 60)
    print("🎮 HARRY POTTER MULTIPLAYER SERVER")
    print("=" * 60)
    print(f"\n✅ Сервер запущен!")
    print(f"\n📍 Локальный IP: {local_ip}")
    print(f"📍 Порт: {port}")
    print(f"\n🖥️  На этом компьютере используй:")
    print(f"   ws://localhost:{port}/game")
    print(f"\n📱 На телефоне/другом устройстве используй:")
    print(f"   ws://{local_ip}:{port}/game")
    print(f"\n🌐 Для доступа с телефона открой в браузере:")
    print(f"   http://{local_ip}:{port}/")
    print("\n⚠️  Убедись, что телефон в той же WiFi сети!")
    print("=" * 60)
    print("\nДля остановки нажми Ctrl+C\n")
    
    # Запускаем сервер на всех интерфейсах (0.0.0.0)
    uvicorn.run(app, host='0.0.0.0', port=port)
