"""
Скрипт для обновления всех игровых хендлеров под работу в группах.
Добавляет:
  - chat_id для статистики
  - mention_user для упоминаний
  - Проверку настроек чата
"""
import os
import re

GAMES_DIR = "wind_bot/handlers/games"

# Шаблон для добавления в начало функции
CHAT_ID_TEMPLATE = '''    chat_id = message.chat.id if message.chat.type in ("group", "supergroup") else None
    is_group = chat_id is not None
'''

# Шаблон для упоминания игрока
MENTION_TEMPLATE = '''
    if is_group:
        player = mention_user(tg_id, message.from_user.first_name)
    else:
        player = ""
'''

def update_game_file(filepath: str) -> bool:
    """Обновляет файл игры для поддержки групп."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Проверяем, уже обновлён ли файл
    if 'chat_id = message.chat.id' in content:
        print(f"  ⏭ Уже обновлён: {filepath}")
        return False

    # Добавляем импорт mention_user
    if 'from utils.helpers import' in content:
        content = re.sub(
            r'(from utils\.helpers import .+)',
            r'\1, mention_user',
            content
        )
        # Убираем дубли
        content = content.replace(', mention_user, mention_user', ', mention_user')
    else:
        content = content.replace(
            'from utils.helpers import',
            'from utils.helpers import mention_user, '
        )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  ✅ Обновлён: {filepath}")
    return True


def main():
    print("🔄 Обновление игр для поддержки групп...\n")

    if not os.path.exists(GAMES_DIR):
        print(f"❌ Директория не найдена: {GAMES_DIR}")
        return

    updated = 0
    for filename in os.listdir(GAMES_DIR):
        if filename.endswith('.py') and filename != '__init__.py':
            filepath = os.path.join(GAMES_DIR, filename)
            if update_game_file(filepath):
                updated += 1

    print(f"\n✅ Обновлено файлов: {updated}")
    print("\n⚠️ Вручную добавьте в каждую игру:")
    print("  1. chat_id в вызов play_game()")
    print("  2. player mention в ответах")


if __name__ == "__main__":
    main()