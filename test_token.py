"""Диагностика токена."""
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("BOT_TOKEN", "")

print(f"Длина токена: {len(token)}")
print(f"Токен (первые 10 символов): '{token[:10]}...'")
print(f"Токен (последние 5 символов): '...{token[-5:]}'")
print(f"Repr токена: {repr(token)}")
print(f"Содержит пробелы по краям: {token != token.strip()}")
print(f"Содержит кавычки: {'\"' in token or chr(39) in token}")

# Проверяем формат: число:строка
if ":" in token:
    parts = token.split(":", 1)
    print(f"ID бота: '{parts[0]}' (должно быть число)")
    print(f"ID бота — число: {parts[0].strip().isdigit()}")
else:
    print("❌ В токене НЕТ двоеточия — формат неверный!")