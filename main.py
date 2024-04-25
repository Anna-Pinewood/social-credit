import datetime
import telebot
import sqlite3
from telebot import types

# Оригинальный токен
TELEGRAM_TOKEN = "6389468643:AAEDBmG6fSwSoFflAgtjZhVpmC6FN9axGJ4"
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Список пользователей
names = ['Макс', 'Оля', 'Никита']
# Опции реакций
options = {'like': '👍', 'dislike': '👎'}
# Словарь состояний пользователей
user_states = {}


# Функция для создания базы данных
def create_table():
    conn = sqlite3.connect('reactions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reactions 
                 (user_id INTEGER, person TEXT, reaction TEXT, comment TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()


create_table()


@bot.message_handler(commands=['help'])
def help_message(message):
    help_text = "Доступны два сценария: оценка и статистика. Для запуска любого из сценариев сначала необходимо ввести команду /start."
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(commands=['start'])
def start_message(message):
    keyboard = types.InlineKeyboardMarkup()
    key_yes = types.InlineKeyboardButton(
        text='Отреагировать', callback_data='react')
    keyboard.add(key_yes)
    key_no = types.InlineKeyboardButton(text='Статистика', callback_data='no')
    keyboard.add(key_no)
    question = "Что вы хотите сделать?"
    bot.send_message(message.from_user.id, text=question,
                     reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "react":
        user_states[call.from_user.id] = "reaction"
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(
            name, callback_data=name) for name in names]
        keyboard.add(*buttons)
        bot.send_message(
            call.message.chat.id, "Какого пользователя вы хотите оценить?", reply_markup=keyboard)

    elif call.data in names and user_states.get(call.from_user.id) == "reaction":
        user_states[call.from_user.id] = "reaction_result"
        user_states['target_user'] = call.data
        bot.send_message(call.message.chat.id,
                         f"Вы выбрали оценить {call.data}")

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        buttons = [types.InlineKeyboardButton(
            symbol, callback_data=option) for option, symbol in options.items()]
        keyboard.add(*buttons)
        bot.send_message(
            call.message.chat.id, "Как вы оцениваете действие пользователя?", reply_markup=keyboard)

    elif call.data in options and user_states.get(call.from_user.id) == "reaction_result":
        user_states[call.from_user.id] = "comment"
        bot.send_message(call.message.chat.id, f"Вы поставили {call.data}")
        user_states['reaction'] = call.data
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        skip_button = types.InlineKeyboardButton(
            "Пропустить", callback_data='skip')
        keyboard.add(skip_button)
        bot.send_message(call.message.chat.id, "Напишите комментарий или нажмите кнопку Пропустить",
                         reply_markup=keyboard)

    elif call.data == "skip" and user_states.get(call.from_user.id) == "comment":
        bot.send_message(call.message.chat.id, "Вы пропустили комментарий.")
        user_id = call.from_user.id
        person = user_states['target_user']
        reaction = user_states['reaction']
        comment = None
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_to_db(user_id, person, reaction, comment, timestamp)
        bot.send_message(call.message.chat.id, f"Записано.")
        user_states[call.from_user.id] = None
        bot.send_message(call.message.chat.id,
                         f"Для нового взаимодействия отправьте /start.")

    elif call.data == "no":
        # Вывод статистики
        conn = sqlite3.connect('reactions.db')
        c = conn.cursor()
        c.execute("SELECT person, SUM(CASE WHEN reaction='like' THEN 1 ELSE 0 END) AS likes, SUM(CASE WHEN reaction='dislike' THEN 1 ELSE 0 END) AS dislikes FROM reactions GROUP BY person")
        rows = c.fetchall()
        stat_message = "\n".join(
            [f"{row[0]}: {row[1]} likes, {row[2]} dislikes" for row in rows])
        print(stat_message)
        if stat_message == "":
            bot.send_message(call.message.chat.id, 'Статистика пуста.')
        else:
            bot.send_message(call.message.chat.id, stat_message)
        conn.close()
        bot.send_message(call.message.chat.id,
                         f"Для нового взаимодействия отправьте /start.")


@bot.message_handler(content_types=['text'])
def handle_text(message):
    if user_states.get(message.from_user.id) == "comment":

        bot.send_message(message.chat.id,
                         f"Ваш комментарий: {message.text}.")
        # Запись данных в базу данных

        user_id = message.from_user.id
        person = user_states['target_user']
        reaction = user_states['reaction']
        comment = message.text if message.text != "пропустить" else None
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_to_db(user_id, person, reaction, comment, timestamp)

        bot.send_message(
            message.chat.id, f"Записано.")
        # Сброс состояния после обработки комментария
        user_states[message.from_user.id] = None
        bot.send_message(user_id,
                         f"Для нового взаимодействия отправьте /start.")


def write_to_db(user_id, person, reaction, comment, timestamp):
    conn = sqlite3.connect('reactions.db')
    c = conn.cursor()
    print(user_id, person, reaction, comment, timestamp)
    c.execute("INSERT INTO reactions (user_id, person, reaction, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
              (user_id, person, reaction, comment, timestamp))
    conn.commit()
    conn.close()


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.from_user.id not in user_states:
        bot.send_message(
            message.chat.id, "Доступны два сценария: оценка и статистика. Для запуска любого из сценариев сначала необходимо ввести команду /start.")


bot.polling(none_stop=True, interval=0)
