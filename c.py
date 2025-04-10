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

# Список заблокованих слів (спам)
BLOCKED_WORDS = ["спам", "непотрібне слово", "погроза"]  # Додайте свої слова

# Словник для зберігання відповідей користувача
users = {}

# ID адміністраторів бота
ADMIN_USERS = [5219622676]  # Додайте сюди свій ID

# Функція для перевірки на спам
def is_spam(text):
    """
    Перевірка, чи містить текст заборонені слова.
    
    Параметри:
    - text: введений текст
    
    Повертає:
    - True, якщо знайдено заборонене слово
    - False, якщо немає
    """
    for word in BLOCKED_WORDS:
        if word.lower() in text.lower():
            return True
    return False

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

# Обробка введених даних
async def handle_input(update, context):
    """
    Обробник введених даних користувачем.
    Валідує введення, зберігає відповіді та переходить до наступного кроку.
    """
    user_id = update.effective_user.id
    text = update.message.text
    
    # Перевірка на спам
    if is_spam(text):
        await update.message.reply_text("Це повідомлення містить заборонене слово. Ви заблоковані.")
        # Можна також заблокувати користувача або відправити попередження
        return

    # Перевірка чи користувач почав сесію
    if user_id not in users:
        await update.message.reply_text("Будь ласка, натисніть /start, щоб розпочати роботу з калькулятором.")
        return
    
    # Отримання поточного кроку
    step = users[user_id]['step']
    
    # Парсинг введеного значення
    value, success = parse_numeric_input(text)
    
    # Перевірка успішності парсингу
    if not success:
        await update.message.reply_text("Будь ласка, введіть число. Якщо витрати відсутні (дорівнюють нулю), введіть цифру 0.")
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

# Головна функція для запуску бота
def main():
    """
    Головна функція для запуску бота.
    """
    # Отримання токену з змінних середовища
    TOKEN = os.environ.get('TELEGRAM_TOKEN')
    
    if not TOKEN:
        # Якщо токен не знайдено, використовуємо фіксований токен для тестів
        TOKEN = "7930140233:AAEsNNbsGS7oQgbiR9q_scPYZtOqfYDSiKg"  # Ваш токен
    
    # Створення екземпляру застосунку
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button, pattern=START_CALCULATION))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    
    # Запуск бота
    print("Бот запущено...")
    application.run_polling()

if __name__ == "__main__":
    main()