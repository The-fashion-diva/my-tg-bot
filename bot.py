import telebot
from telebot import types
import json
import os
import random
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

try:
    import config
    ADMIN_IDS = config.ADMIN_IDS
except (ImportError, AttributeError):
    ADMIN_IDS = []

CARDS_FILE = 'cards_data.json'
RARITY_PROBS = {'R': 0.4, 'SR': 0.275, 'SSR': 0.2, 'UR': 0.125}
RARITY_REWARDS = {
    'R': {'exp': 10, 'coins': 5},
    'SR': {'exp': 25, 'coins': 10},
    'SSR': {'exp': 50, 'coins': 30},
    'UR': {'exp': 100, 'coins': 50}
}
CARD_COOLDOWN = 6 * 60 * 60
DATA_FILE = 'users_data.json'

ITEMS = {
    '1': {'name': 'Маленькое зелье', 'price': 20, 'description': 'Даёт +10 опыта при следующей карточке (автоматически)'},
    '2': {'name': 'Счастливый билет', 'price': 50, 'description': 'Позволяет получить карточку вне очереди (один раз)'},
    '3': {'name': 'Золотая подкова', 'price': 100, 'description': 'Увеличивает шанс выпадения редкой карточки на 10% (пассивно)'},
}

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
            'last_card_time': 0,
            'experience': 0,
            'coins': 0,
            'favorite_card': None,
            'inventory': []
        }
        save_users_data(users)
    else:
        updated = False
        if 'experience' not in users[user_id_str]:
            users[user_id_str]['experience'] = 0
            updated = True
        if 'coins' not in users[user_id_str]:
            users[user_id_str]['coins'] = 0
            updated = True
        if 'favorite_card' not in users[user_id_str]:
            users[user_id_str]['favorite_card'] = None
            updated = True
        if 'last_card_time' not in users[user_id_str]:
            users[user_id_str]['last_card_time'] = 0
            updated = True
        if 'inventory' not in users[user_id_str]:
            users[user_id_str]['inventory'] = []
            updated = True
        if updated:
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
    available = []
    for card in cards:
        if card['name'] not in user_cards:
            available.append(card)
    return available

def draw_card(user_cards):
    available_cards = get_available_cards(user_cards)
    if not available_cards:
        return None
    cards_by_rarity = {}
    for card in available_cards:
        rarity = card['rarity']
        if rarity not in cards_by_rarity:
            cards_by_rarity[rarity] = []
        cards_by_rarity[rarity].append(card)
    available_rarities = list(cards_by_rarity.keys())
    if not available_rarities:
        return None
    probs = {r: RARITY_PROBS.get(r, 0) for r in available_rarities}
    total_prob = sum(probs.values())
    normalized_probs = [probs[r] / total_prob for r in available_rarities]
    chosen_rarity = random.choices(
        population=available_rarities,
        weights=normalized_probs
    )[0]
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
    bot.reply_to(message, f'✅ Карточка "{card_name}" успешно удалена! Примечание: у пользователей, которые уже собрали эту карту, она останется в данных, но не будет отображаться в коллекции, пока не будет добавлена вновь.')

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

# --- Команда для установки любимой карточки ---
@bot.message_handler(commands=['setfavorite'])
def set_favorite(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)
    if not user_data['cards']:
        bot.reply_to(message, "У вас пока нет карточек. Сначала получите карточку через /getcard.")
        return
    text = message.text.strip()
    if len(text.split()) < 2:
        bot.reply_to(message, "Пожалуйста, укажите название карточки после команды. Например: /setfavorite Сумеречная Искорка")
        return
    card_name = text.split(' ', 1)[1].strip()
    found = None
    for name in user_data['cards'].keys():
        if name.lower() == card_name.lower():
            found = name
            break
    if not found:
        bot.reply_to(message, f"У вас нет карточки с названием «{card_name}». Проверьте написание.")
        return
    # Проверяем, существует ли карта в общем списке (иначе любимую ставить нельзя)
    if not any(c['name'] == found for c in cards):
        bot.reply_to(message, f"Карточка «{found})» была удалена из игры и не может быть любимой.")
        return
    user_data['favorite_card'] = found
    update_user_data(user_id, user_data)
    bot.reply_to(message, f"✅ Любимая карточка установлена: {found}")

# --- Команда для просмотра конкретной карточки ---
@bot.message_handler(commands=['viewcard'])
def view_card(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)
    text = message.text.strip()
    if len(text.split()) < 2:
        bot.reply_to(message, "Пожалуйста, укажите название карточки. Например: /viewcard Сумеречная Искорка")
        return
    card_name = text.split(' ', 1)[1].strip()
    found_name = None
    for name in user_data['cards'].keys():
        if name.lower() == card_name.lower():
            found_name = name
            break
    if not found_name:
        bot.reply_to(message, f"У вас нет карточки с названием «{card_name}».")
        return
    # Ищем в общем списке
    card_data = next((c for c in cards if c['name'] == found_name), None)
    if not card_data:
        bot.reply_to(message, f"Карточка «{found_name})» больше не доступна в игре (удалена).")
        return
    count = user_data['cards'][found_name]
    caption = f"🃏 {found_name}\nРедкость: {card_data['rarity']}\nУ вас: {count} шт."
    if "image_id" in card_data:
        bot.send_photo(message.chat.id, card_data["image_id"], caption=caption)
    else:
        bot.send_message(message.chat.id, caption)

# --- Команда магазина ---
@bot.message_handler(commands=['market'])
def show_market(message):
    text = "🏪 Магазин предметов:\n\n"
    for item_id, item in ITEMS.items():
        text += f"🆔 {item_id}. {item['name']} – {item['price']} 🪙\n   {item['description']}\n\n"
    text += "Купить: /buy [ID предмета]"
    bot.reply_to(message, text)

@bot.message_handler(commands=['buy'])
def buy_item(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)
    text = message.text.strip()
    if len(text.split()) < 2:
        bot.reply_to(message, "Укажите ID предмета. Например: /buy 1")
        return
    item_id = text.split()[1].strip()
    if item_id not in ITEMS:
        bot.reply_to(message, "Предмет с таким ID не найден.")
        return
    item = ITEMS[item_id]
    price = item['price']
    if user_data['coins'] < price:
        bot.reply_to(message, f"Недостаточно монет. У вас {user_data['coins']} 🪙, нужно {price}.")
        return
    user_data['coins'] -= price
    user_data['inventory'].append(item_id)
    update_user_data(user_id, user_data)
    bot.reply_to(message, f"✅ Вы купили {item['name']}! Остаток монет: {user_data['coins']} 🪙")
    # --- Команда инвентаря ---
@bot.message_handler(commands=['inventory'])
def show_inventory(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)
    inv = user_data.get('inventory', [])
    if not inv:
        bot.reply_to(message, "Ваш инвентарь пуст. Зайдите в /market.")
        return
    text = "🎒 Ваш инвентарь:\n"
    for item_id in inv:
        if item_id in ITEMS:
            text += f"• {ITEMS[item_id]['name']}\n"
        else:
            text += f"• Неизвестный предмет (ID {item_id})\n"
    bot.reply_to(message, text)

# --- Команда профиля (с фото любимой карточки) ---
@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)
    
    # Считаем только актуальные карты (которые есть в общем списке)
    total_cards_count = 0
    for name, count in user_data['cards'].items():
        if any(c['name'] == name for c in cards):
            total_cards_count += count
    
    experience = user_data.get('experience', 0)
    coins = user_data.get('coins', 0)
    favorite = user_data.get('favorite_card')
    # Проверяем, что любимая карта ещё существует
    if favorite and not any(c['name'] == favorite for c in cards):
        favorite = None
    inv_count = len(user_data.get('inventory', []))
    
    level = (experience // 100) + 1
    next_level_exp = (level) * 100
    
    profile_text = (
        f"👤 Профиль игрока\n"
        f"❤️ Любимая карточка: {favorite if favorite else 'не выбрана'}\n"
        f"📊 Уровень: {level}\n"
        f"✨ Опыт: {experience} / {next_level_exp}\n"
        f"🪙 Монеты: {coins}\n"
        f"🃏 Всего карточек: {total_cards_count}\n"
        f"🎒 Предметов: {inv_count}"
    )
    
    if favorite:
        card_data = next((c for c in cards if c['name'] == favorite), None)
        if card_data and "image_id" in card_data:
            bot.send_photo(message.chat.id, card_data["image_id"], caption=profile_text)
            return
    bot.reply_to(message, profile_text)

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
        "• За каждую новую карточку вы получаете опыт и монеты!\n"
        "• Монеты можно тратить в магазине (/market)\n"
        "• Ваша коллекция сохраняется, её можно посмотреть командой /collection\n"
        "• Команда /profile покажет ваш профиль и любимую карточку\n"
        "• Установить любимую карточку: /setfavorite Название\n"
        "• Посмотреть карточку: /viewcard Название\n\n"
        "Удачи в сборе! 🍀"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['getcard'])
def give_card(message):
    user_id = message.from_user.id
    users, user_data = get_user_data(user_id)
    
    can_get, remaining = can_get_card(user_data)
    if not can_get:
        time_str = format_time(remaining)
        bot.reply_to(message, f'Вы оглянулись, но не увидели никого из пони рядом. ⏳ Следующую карточку можно будет получить через {time_str}.')
        return
    
    user_cards = user_data['cards']
    available_cards = get_available_cards(user_cards)
    if not available_cards:
        bot.reply_to(message, "🌟 Поздравляем! Вы собрали ВСЕ карточки! Ждите добавления новых.")
        return
    
    card = draw_card(user_cards)
    if not card:
        bot.reply_to(message, "😕 Что-то пошло не так. Попробуйте позже.")
        return
    
    card_name = card['name']
    card_rarity = card['rarity']
    user_data['cards'][card_name] = user_data['cards'].get(card_name, 0) + 1
    
    reward = RARITY_REWARDS.get(card_rarity, {'exp': 0, 'coins': 0})
    user_data['experience'] = user_data.get('experience', 0) + reward['exp']
    user_data['coins'] = user_data.get('coins', 0) + reward['coins']
    
    user_data['last_card_time'] = int(time.time())
    update_user_data(user_id, user_data)

    caption = f"🎉 Вы получили новую карточку: {card_name}\nРедкость: {card_rarity}"
    caption += f"\n✨ +{reward['exp']} опыта, 🪙 +{reward['coins']} монет"
    
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
    # Фильтруем: показываем только те карты, которые есть в общем списке
    for card_name, count in sorted(cards_dict.items()):
        card_info = next((c for c in cards if c["name"] == card_name), None)
        if not card_info:
            continue  # пропускаем удалённые карты
        rarity = card_info["rarity"]
        lines.append(f"• {card_name} ({rarity}) — {count} шт.")
        total += count

    if len(lines) == 1:  # не добавилось ни одной карты
        bot.reply_to(message, "В вашей коллекции пока нет актуальных карт (возможно, они были удалены).")
        return

    total_cards = len(cards)
    collected = sum(1 for name in cards_dict if any(c["name"] == name for c in cards))
    percent = int(collected/total_cards*100) if total_cards > 0 else 0
    lines.append(f"\nВсего карточек: {total}")
    lines.append(f"Прогресс: собрано {collected} из {total_cards} уникальных карточек ({percent}%)")
    
    bot.reply_to(message, "\n".join(lines))

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    bot.reply_to(message, "Используй команды /getcard, /collection, /profile, /setfavorite, /viewcard, /market, /inventory, /buy; для админа: /addcard, /removecard, /reset_cooldown")

if __name__ == '__main__':
    print("Бот запущен...")
    print(f"Доступно карточек: {len(cards)}")
    print(f"Администраторы: {ADMIN_IDS if ADMIN_IDS else 'не назначены'}")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Ошибка: {e}")
