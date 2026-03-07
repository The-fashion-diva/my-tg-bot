import telebot
from telebot import types
import json
import os
import random
from datetime import datetime, timedelta
import sys
import time

TOKEN = '8772998450:AAH5cetqz9qei-vxFImztQxmf8EE5TLUtzA'
if not TOKEN:
    try:
        import config
        TOKEN = config.TOKEN
    except ImportError:
        print('Ошибка: не удалось найти токен')
        sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# Пытаемся импортировать config для ADMIN_IDS
try:
    import config
    ADMIN_IDS = config.ADMIN_IDS
except (ImportError, AttributeError):
    ADMIN_IDS = []

CARDS_FILE = 'cards_data.json'
RARITY_PROBS = {'R': 0.4, 'SR': 0.275, 'SSR': 0.2, 'UR': 0.125}
CARD_COOLDOWN = 6 * 60 * 60
DATA_FILE = 'users_data.json'

def load_cards():
    if not os.path.exists(CARDS_FILE):
        default_cards = [
            {'name': 'Зекора', 'rarity': 'R'},
            {'name': 'Свити Белль', 'rarity': 'SR'},
            {'name': 'Сумеречная Искорка', 'rarity': 'SSR'},
            {'name': 'Спайк', 'rarity': 'R'},
        ]
        save_cards(default_cards)
        return default_cards
    try:
        with open(CARDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f'Ошибка загрузки карточек: {e}')
        return []

def save_cards(cards_list):
    try:
        with open(CARDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(cards_list, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f'Ошибка сохранения карточек: {e}')

cards = load_cards()

def load_users_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f'Ошибка загрузки данных: {e}')
        return {}

def save_users_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f'Ошибка сохранения данных: {e}')

def get_user_data(user_id):
    users = load_users_data()
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            'cards': {},
            'last_card_time': 0
        }
        save_users_data(users)
    return users, users[user_id_str]

def update_user_data(user_id, updated_data):
    users = load_users_data()
    users[str(user_id)] = updated_data
    save_users_data(users)

def can_get_card(user_data):
    current_time = int(time.time())
    last_time = user_data.get('last_card_time', 0)
    time_passed = current_time - last_time
    if time_passed >= CARD_COOLDOWN:
        return True, 0
    else:
        remaining = CARD_COOLDOWN - time_passed
        return False, remaining

def format_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f'{hours} ч {minutes} мин'
    else:
        return f'{minutes} мин'

def get_available_cards(user_cards):
    """
    Возвращает список карточек, которых ещё нет у пользователя.
    """
    available = []
    for card in cards:
        if card['name'] not in user_cards:
            available.append(card)
    return available

def draw_card(user_cards):
    """
    Выбирает случайную карточку из тех, которых ещё нет у пользователя,
    с учётом вероятностей редкости.
    """
    available_cards = get_available_cards(user_cards)
    
    if not available_cards:
        return None  # Все карточки собраны
    
    # Группируем доступные карточки по редкости
    cards_by_rarity = {}
    for card in available_cards:
        rarity = card['rarity']
        if rarity not in cards_by_rarity:
            cards_by_rarity[rarity] = []
        cards_by_rarity[rarity].append(card)
        # Выбираем редкость согласно вероятностям
    # Но учитываем только те редкости, которые ещё доступны
    available_rarities = list(cards_by_rarity.keys())
    if not available_rarities:
        return None
    
    # Создаём список вероятностей только для доступных редкостей
    probs = {r: RARITY_PROBS.get(r, 0) for r in available_rarities}
    # Нормализуем вероятности, чтобы их сумма была 1
    total_prob = sum(probs.values())
    normalized_probs = [probs[r] / total_prob for r in available_rarities]
    
    chosen_rarity = random.choices(
        population=available_rarities,
        weights=normalized_probs
    )[0]
    
    # Выбираем случайную карточку из выбранной редкости
    return random.choice(cards_by_rarity[chosen_rarity])

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- Добавление карточек ---
admin_add_state = {}

@bot.message_handler(commands=['addcard'])
def add_card_start(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ У вас нет прав администратора.")
        return
    admin_add_state[user_id] = {}
    bot.reply_to(message, "Введите название новой карточки (или /cancel для отмены):")
    bot.register_next_step_handler(message, process_add_card_name)

def process_add_card_name(message):
    user_id = message.from_user.id
    if message.text == '/cancel':
        bot.reply_to(message, '❌ Добавление отменено.')
        admin_add_state.pop(user_id, None)
        return
    if message.content_type != 'text':
        bot.reply_to(message, 'Пожалуйста, введите название текстом.')
        bot.register_next_step_handler(message, process_add_card_name)
        return
    name = message.text.strip()
    if not name:
        bot.reply_to(message, 'Название не может быть пустым. Введите название снова:')
        bot.register_next_step_handler(message, process_add_card_name)
        return
    if any(card['name'].lower() == name.lower() for card in cards):
        bot.reply_to(message, '❌ Карточка с таким названием уже существует. Введите другое название:')
        bot.register_next_step_handler(message, process_add_card_name)
        return
    admin_add_state[user_id]['name'] = name
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('R', 'SR', 'SSR', 'UR')
    bot.reply_to(message, 'Выберите редкость карточки:', reply_markup=markup)
    bot.register_next_step_handler(message, process_add_card_rarity)

def process_add_card_rarity(message):
    user_id = message.from_user.id
    if message.content_type != 'text':
        bot.reply_to(message, 'Пожалуйста, выберите редкость, используя кнопки.')
        bot.register_next_step_handler(message, process_add_card_rarity)
        return
    rarity = message.text.strip().upper()
    if rarity not in ['R', 'SR', 'SSR', 'UR']:
        bot.reply_to(message, '❌ Некорректная редкость. Выберите R, SR, SSR или UR:')
        bot.register_next_step_handler(message, process_add_card_rarity)
        return
    admin_add_state[user_id]['rarity'] = rarity
    bot.reply_to(message, 'Отправьте изображение для карточки (или отправьте /skip, чтобы пропустить)')
    bot.register_next_step_handler(message, process_add_card_image)

def process_add_card_image(message):
    user_id = message.from_user.id
    if message.text == '/skip':
        admin_add_state[user_id]['image_id'] = None
        save_new_card(user_id)
        return
    if message.photo:
        file_id = message.photo[-1].file_id
        admin_add_state[user_id]['image_id'] = file_id
        save_new_card(user_id)
    else:
        bot.reply_to(message, "❌ Пожалуйста, отправьте изображение или /skip:")
        bot.register_next_step_handler(message, process_add_card_image)

def save_new_card(user_id):
    data = admin_add_state.pop(user_id, None)
    if not data:
        return
    new_card = {
        "name": data['name'],
        "rarity": data['rarity'],
    }
    if data.get('image_id'):
        new_card["image_id"] = data['image_id']
    cards.append(new_card)
    save_cards(cards)
    bot.send_message(user_id, f"✅ Карточка «{data['name']}» успешно добавлена!")

# --- Удаление карточек ---
admin_remove_state = {}

@bot.message_handler(commands=['removecard'])
def remove_card_start(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ У вас нет прав администратора.")
        return
    bot.reply_to(message, "Введите название карточки, которую хотите удалить (или /cancel для отмены):")
    bot.register_next_step_handler(message, process_remove_card_name)

def process_remove_card_name(message):
    user_id = message.from_user.id
    if message.text == '/cancel':
        bot.reply_to(message, '❌ Удаление отменено.')
        admin_remove_state.pop(user_id, None)
        return
    if message.content_type != 'text':
        bot.reply_to(message, 'Пожалуйста, введите название текстом.')
        bot.register_next_step_handler(message, process_remove_card_name)
        return
    name = message.text.strip()
    found = None
    for card in cards:
        if card['name'].lower() == name.lower():
            found = card
            break
    if not found:
        bot.reply_to(message, f'❌ Карточка с названием "{name}" не найдена. Введите другое название:')
        bot.register_next_step_handler(message, process_remove_card_name)
        return
    admin_remove_state[user_id] = found['name']
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('Да', 'Нет')
    bot.reply_to(message, f'Вы уверены, что хотите удалить карточку "{found["name"]}"?\nЭто действие необратимо.', reply_markup=markup)
    bot.register_next_step_handler(message, confirm_remove_card)

def confirm_remove_card(message):
    user_id = message.from_user.id
    if message.content_type != 'text':
        bot.reply_to(message, 'Пожалуйста, ответьте "Да" или "Нет".')
        bot.register_next_step_handler(message, confirm_remove_card)
        return
    answer = message.text.strip().lower()
    if answer not in ['да', 'нет']:
        bot.reply_to(message, 'Пожалуйста, ответьте "Да" или "Нет".')
        bot.register_next_step_handler(message, confirm_remove_card)
        return
    if answer == 'нет':
        bot.reply_to(message, '❌ Удаление отменено.')
        admin_remove_state.pop(user_id, None)
        return
    card_name = admin_remove_state.pop(user_id, None)
    if not card_name:
        bot.reply_to(message, 'Произошла ошибка. Попробуйте снова.')
        return
    global cards
    cards = [card for card in cards if card['name'] != card_name]
    save_cards(cards)
    bot.reply_to(message, f'✅ Карточка "{card_name}" успешно удалена!')

# --- Сброс кулдауна для админа ---
@bot.message_handler(commands=['reset_cooldown'])
def reset_cooldown(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ У вас нет прав администратора.")
        return
    users, user_data = get_user_data(user_id)
    user_data['last_card_time'] = 0
    update_user_data(user_id, user_data)
    bot.reply_to(message, f"✅ Время ожидания сброшено. Теперь вы можете сразу получить карточку командой /getcard.")

# --- Основные команды для всех ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "🎴 Добро пожаловать в коллекционную игру с карточками по вселенной My Little Pony: friendship is magic!\n\n"
        "Правила:\n"
        "• Каждые 6 часов можно получить одну карточку с помощью команды /getcard\n"
        "• Карточки бывают четырёх редкостей: Редкая (R), Суперредкая (SR), Эпическая (SSR) и Легендарная (UR)\n"
        "• Вероятность выпадения: Редкая - 40%, Суперредкая - 27,5%, Эпическая - 20%, Легендарная - 12,5%\n"
        "• Вы не можете получить карточку, которая уже есть в вашей коллекции\n"
        "• Ваша коллекция сохраняется, её можно посмотреть командой /collection\n\n"
        "Удачи в сборе! 🍀"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['getcard'])
def give_card(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)
    
    # Проверяем, прошло ли 6 часов
    can_get, remaining = can_get_card(user_data)
    if not can_get:
        time_str = format_time(remaining)
        bot.reply_to(message, f'Вы оглянулись, но не увидели никого из пони рядом. ⏳ Следующую карточку можно будет получить через {time_str}.')
        return
    
    # Получаем коллекцию пользователя
    user_cards = user_data['cards']
    
    # Проверяем, есть ли ещё доступные карточки
    available_cards = get_available_cards(user_cards)
    if not available_cards:
        bot.reply_to(message, "🌟 Поздравляем! Вы собрали ВСЕ карточки! Ждите добавления новых.")
        return
    
    # Выбираем карточку из доступных
    card = draw_card(user_cards)
    if not card:
        bot.reply_to(message, "😕 Что-то пошло не так. Попробуйте позже.")
        return
    
    card_name = card['name']
    card_rarity = card['rarity']

    # Добавляем карточку в коллекцию
    user_data['cards'][card_name] = user_data['cards'].get(card_name, 0) + 1
    user_data['last_card_time'] = int(time.time())
    update_user_data(user_id, user_data)

    # Отправляем карточку пользователю
    caption = f"🎉 Вы получили новую карточку: {card_name}\nРедкость: {card_rarity}"
    
    # Показываем, сколько ещё осталось собрать
    remaining_count = len(available_cards) - 1
    if remaining_count > 0:
        caption += f"\nОсталось собрать: {remaining_count} карточек"
    else:
        caption += f"\n🌟 Осталась последняя карточка!"
    
    if "image_id" in card:
        bot.send_photo(message.chat.id, card["image_id"], caption=caption)
    else:
        bot.send_message(message.chat.id, caption)

@bot.message_handler(commands=['collection'])
def show_collection(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)

    cards_dict = user_data["cards"]
    if not cards_dict:
        bot.reply_to(message, "Ваша коллекция пуста. Начните собирать карточки с помощью /getcard!")
        return

    lines = ["📋 Ваша коллекция:"]
    total = 0
    for card_name, count in sorted(cards_dict.items()):
        rarity = next((c["rarity"] for c in cards if c["name"] == card_name), "unknown")
        lines.append(f"• {card_name} ({rarity}) — {count} шт.")
        total += count
    
    # Добавляем информацию о прогрессе
    total_cards = len(cards)
    collected = len(cards_dict)
    lines.append(f"\nВсего карточек: {total}")
    lines.append(f"Прогресс: собрано {collected} из {total} уникальных карточек ({int(collected/total*100)}%)")
    
    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    bot.reply_to(message, "Используй команды /getcard, /collection или /addcard, /removecard, /reset_cooldown (для админа)")

if __name__ == '__main__':
    print("Бот запущен...")
    print(f"Доступно карточек: {len(cards)}")
    print(f"Администраторы: {ADMIN_IDS if ADMIN_IDS else 'не назначены'}")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Ошибка: {e}")
