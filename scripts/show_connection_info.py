"""
Генератор QR-кода для быстрого подключения с телефона
"""
try:
    import qrcode
    from PIL import Image
    has_qr = True
except ImportError:
    has_qr = False
    print("⚠️  Для QR-кода установите: pip install qrcode[pil]")

import socket

def get_local_ip():
    """Получает локальный IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"

def generate_qr_code():
    """Создаёт QR-код с адресом игры"""
    if not has_qr:
        return False
    
    local_ip = get_local_ip()
    game_url = f"http://{local_ip}:8003/"
    
    # Создаём QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(game_url)
    qr.make(fit=True)
    
    # Генерируем изображение
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("game_qr_code.png")
    
    print("=" * 60)
    print("✅ QR-код создан: game_qr_code.png")
    print(f"📱 Отсканируй QR-код на телефоне для быстрого доступа")
    print(f"🌐 URL: {game_url}")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8003
    
    print("\n" + "=" * 60)
    print("📱 ИНСТРУКЦИЯ ДЛЯ ПОДКЛЮЧЕНИЯ С ТЕЛЕФОНА")
    print("=" * 60)
    
    print(f"\n🖥️  Ваш локальный IP: {local_ip}")
    print(f"📍 Порт сервера: {port}")
    
    print(f"\n📱 На телефоне откройте браузер и введите:")
    print(f"\n   http://{local_ip}:{port}/")
    print(f"\n   ИЛИ в поле 'Адрес сервера' в игре:")
    print(f"   ws://{local_ip}:{port}/game")
    
    print("\n⚠️  ВАЖНО:")
    print("   1. Телефон должен быть в той же WiFi сети")
    print("   2. Сервер должен быть запущен (python start_multiplayer.py)")
    print("   3. Room ID должен быть одинаковый у всех игроков")
    
    print("\n🎮 Порядок действий:")
    print("   1. Запустить сервер на ПК (start_multiplayer.py)")
    print("   2. На телефоне открыть адрес выше")
    print("   3. Ввести имя и Room ID")
    print("   4. Играть!")
    
    if has_qr:
        print("\n📷 Создаю QR-код для быстрого доступа...")
        if generate_qr_code():
            print("\n✅ Отсканируйте game_qr_code.png камерой телефона!")
    else:
        print("\n💡 Совет: Установите 'pip install qrcode[pil]' для генерации QR-кода")
    
    print("\n" + "=" * 60)
    
    # Копируем адрес в буфер обмена (если возможно)
    try:
        import pyperclip
        url = f"http://{local_ip}:{port}/"
        pyperclip.copy(url)
        print(f"📋 Адрес скопирован в буфер обмена: {url}")
    except:
        pass
    
    print()
