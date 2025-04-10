import os
import threading
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Flask-сервер для підтримки активності на хостингу
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Бот працює! Використовуйте Telegram для взаємодії з ботом."

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app_flask.run(host="0.0.0.0", port=port)

# Запускаємо Flask у окремому потоці
threading.Thread(target=run_flask, daemon=True).start()

# Запитання калькулятора
questions = [
    "1. Введіть вартість використаної пряжі (грн):",
    "2. Введіть товаро-транспортні витрати (грн):",
    "3. Введіть ціну наповнювача за 100 г (грн):",
    "4. Введіть кількість витраченого наповнювача (в грамах):",
    "5. Введіть вартість додаткових матеріалів (грн):",
    "6. Введіть сумарну вартість друкованої продукції (грн):",
    "7. Введіть вартість пакування (грн):",
    "8. Введіть довжину використаної пряжі (в метрах):"
]

# Константи для обробки кнопок
START_CALCULATION = "start_calculation"

# Константи для повідомлень
WELCOME_MESSAGE = """Вітаю! Я калькулятор розрахунку вартості в'язаного виробу.

Я допоможу визначити собівартість вашого виробу, враховуючи вартість пряжі, наповнювача та інших матеріалів.

Для того, щоб розпочати, натисніть кнопку нижче:"""

ERROR_NUMBER_MESSAGE = "Будь ласка, введіть число. Якщо витрати відсутні (дорівнюють нулю), введіть цифру 0."
START_FIRST_MESSAGE = "Будь ласка, натисніть /start, щоб розпочати роботу з калькулятором."
CALCULATION_COMPLETED_TITLE = "Розрахунок завершено:"

# Словник для зберігання відповідей користувача
users = {}

# ID адміністраторів бота
ADMIN_USERS = [5219622676]  # Додайте сюди свій ID

# Коефіцієнт для розрахунку вартості роботи
WORK_PRICE_MULTIPLIER = 1.3

# Перевірка на адміністратора
def is_admin(user_id):
    return user_id in ADMIN_USERS

# Функція для безпечного парсингу чисел
def parse_numeric_input(text):
    """
    Парсить введене користувачем значення як число, обробляючи крапки і коми.
    
    Параметри:
    - text: введений текст
    
    Повертає:
    - число (float)
    - успішність операції (bool)
    """
    if not text or not text.strip():
        return None, False
    
    # Заміна коми на крапку для обробки різних форматів
    cleaned_text = text.replace(",", ".")
    
    try:
        value = float(cleaned_text)
        return value, True
    except ValueError:
        return None, False

# Формат результату
RESULT_FORMAT = """
{title}
- Пряжа: {yarn_cost:.2f} грн
- Транспорт: {transport:.2f} грн
- Наповнювач: {filler_total:.2f} грн
- Додаткові матеріали: {extras:.2f} грн
- Друкована продукція: {printing:.2f} грн
- Пакування: {packaging:.2f} грн
- Робота (довжина x{multiplier}): {work_price:.2f} грн

*Загальна вартість: {total:.2f} грн*

Дякую за використання калькулятора! Для нового розрахунку натисніть /start
"""

# Команда для статистики
async def stats_command(update, context):
    """
    Команда для отримання статистики використання бота.
    Доступна тільки для адміністраторів.
    """
    user_id = update.effective_user.id
    
    # Перевірка прав доступу
    if not is_admin(user_id):
        await update.message.reply_text("У вас немає прав для виконання цієї команди.")
        return
    
    user_count = len(users)
    stats_message = f"""📊 *Статистика використання бота*

👥 Кількість активних користувачів: {user_count}

*Примітка*: Ця статистика обнуляється при перезапуску бота, оскільки дані зберігаються тільки в пам'яті.
"""
    
    await update.message.reply_text(stats_message, parse_mode="Markdown")

# Команда для довідки адміністраторам
async def admin_help(update, context):
    """
    Команда довідки для адміністраторів.
    """
    user_id = update.effective_user.id
    
    # Перевірка прав доступу
    if not is_admin(user_id):
        await update.message.reply_text("У вас немає прав для виконання цієї команди.")
        return
    
    help_message = """*Команди адміністратора*

/stats - показати статистику використання бота
/help_admin - цей список команд

Для використання калькулятора введіть /start"""
    
    await update.message.reply_text(help_message, parse_mode="Markdown")

# Стартова команда
async def start(update, context):
    """
    Обробник команди /start.
    Відправляє привітальне повідомлення з кнопкою для початку розрахунку.
    """
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Створення кнопки для початку розрахунку
    keyboard = [
        [InlineKeyboardButton("Розпочати розрахунок", callback_data=START_CALCULATION)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Відправлення привітального повідомлення
    await update.message.reply_text(
        f"Вітаю, {user_name}! {WELCOME_MESSAGE}", 
        reply_markup=reply_markup
    )

# Обробка натискання на кнопку
async def button(update, context):
    """
    Обробник натискання на кнопку.
    Ініціалізує сесію користувача та запускає процес збору даних.
    """
    query = update.callback_query
    user_id = query.from_user.id
    
    # Ініціалізація даних користувача
    if query.data == START_CALCULATION:
        users[user_id] = {'step': 0, 'answers': []}
        
        # Відправка першого запитання
        await query.answer()
        await query.edit_message_text(text=questions[0])

# Обробка введених даних
async def handle_input(update, context):
    """
    Обробник введених даних користувачем.
    Валідує введення, зберігає відповіді та переходить до наступного кроку.
    """
    user_id = update.effective_user.id
    text = update.message.text
    
    # Перевірка чи користувач почав сесію
    if user_id not in users:
        await update.message.reply_text(START_FIRST_MESSAGE)
        return
    
    # Отримання поточного кроку
    step = users[user_id]['step']
    
    # Парсинг введеного значення
    value, success = parse_numeric_input(text)
    
    # Перевірка успішності парсингу
    if not success:
        await update.message.reply_text(ERROR_NUMBER_MESSAGE)
        return
    
    # Перевірка на від'ємне значення
    if value < 0:
        await update.message.reply_text("Значення не може бути від'ємним. Будь ласка, введіть додатнє число або 0.")
        return
    
    # Додавання відповіді користувача в список
    users[user_id]['answers'].append(value)
    users[user_id]['step'] += 1
    step = users[user_id]['step']
    
    # Перевірка на завершення всіх запитів
    if step < len(questions):
        await update.message.reply_text(questions[step])
    else:
        try:
            # Показуємо всі відповіді для відстеження
            answers = users[user_id]['answers']
            
            # Перевірка кількості відповідей
            if len(answers) != len(questions):
                raise ValueError(f"Неправильна кількість відповідей: {len(answers)}")
            
            # Розрахунок результатів
            yarn_cost = answers[0]
            transport = answers[1]
            filler_price_per_100g = answers[2]
            filler_grams = answers[3]
            extras = answers[4]
            printing = answers[5]
            packaging = answers[6]
            yarn_length = answers[7]
            
            # Безпечні розрахунки наповнювача (з перевіркою нульових значень)
            if filler_grams <= 0 or filler_price_per_100g <= 0:
                filler_total = 0
            else:
                filler_total = (filler_price_per_100g / 100) * filler_grams
            
            # Розрахунок вартості роботи
            if yarn_length <= 0:
                work_price = 0
            else:
                work_price = yarn_length * WORK_PRICE_MULTIPLIER
            
            # Загальна вартість
            total = yarn_cost + transport + filler_total + extras + printing + packaging + work_price
            
            # Форматування і виведення результату
            result_message = RESULT_FORMAT.format(
                title=CALCULATION_COMPLETED_TITLE,
                yarn_cost=yarn_cost,
                transport=transport,
                filler_total=filler_total,
                extras=extras,
                printing=printing,
                packaging=packaging,
                work_price=work_price,
                multiplier=WORK_PRICE_MULTIPLIER,
                total=total
            )
            
            await update.message.reply_text(result_message, parse_mode="Markdown")
        except Exception as e:
            # Обробка помилок в розрахунках
            error_message = f"Вибачте, під час розрахунку сталася помилка: {str(e)}"
            await update.message.reply_text(error_message)
        finally:
            # Видалення даних користувача після завершення
            if user_id in users:
                users.pop(user_id)

def main():
    """
    Головна функція для запуску бота.
    """
    # Отримання токену з змінних середовища
    TOKEN = os.environ.get('TELEGRAM_TOKEN')
    
    if not TOKEN:
        # Якщо токен не знайдено, використовуємо фіксований токен для тестів
        # У реальному додатку цей рядок слід замінити на отримання токену з середовища
        TOKEN = "7930140233:AAEsNNbsGS7oQgbiR9q_scPYZtOqfYDSiKg"  # Ваш токен
    
    # Створення екземпляру застосунку
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button, pattern=START_CALCULATION))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    
    # Адміністративні команди
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("help_admin", admin_help))
    
    # Запуск бота
    print("Бот запущено...")
    application.run_polling()

if __name__ == "__main__":
    main()