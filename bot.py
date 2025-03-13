import os
import sqlite3
import pandas as pd
import requests
from lxml import html
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
DB_NAME = "sites.db"


def init_db():
    """
    Создание базы данных
    """
    with sqlite3.connect(DB_NAME) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    xpath TEXT NOT NULL
                )
            ''')


def save_to_db(data):
    """
    Сохранение данных в базу
    """
    with sqlite3.connect(DB_NAME) as conn:
        with conn:
            cursor = conn.cursor()
            for i, row in data.iterrows():
                cursor.execute('''
                    INSERT INTO sites (title, url, xpath) VALUES (?, ?, ?)
                ''', (row['title'], row['url'], row['xpath']))


def parse_price(url, xpath):
    """
    Парсинг цены по XPath
    """
    try:
        response = requests.get(url)
        tree = html.fromstring(response.content)
        price_text = tree.xpath(xpath)[0].text.strip()  # Очистка цены от лишних символов
        price = float(''.join(filter(lambda x: x.isdigit() or x == '.', price_text)))
        return price
    except Exception as e:
        print(f"Ошибка при парсинге {url}: {e}")
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Функция старта
    """
    keyboard = [["Загрузить файл"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Привет! Нажми 'Загрузить файл', чтобы отправить Excel-файл.",
                                    reply_markup=reply_markup)



async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка файла
    """
    file = await update.message.document.get_file()
    await file.download_to_drive("temp.xlsx")

    try:
        # Чтение файла
        df = pd.read_excel("temp.xlsx")
        if not all(col in df.columns for col in ['title', 'url', 'xpath']):
            await update.message.reply_text("Файл должен содержать колонки: title, url, xpath.")
            return

        # Сохранение в базу
        save_to_db(df)

        # Вывод данных пользователю
        await update.message.reply_text(f"Данные успешно сохранены:\n{df.to_string(index=False)}")

        # Парсинг цен и вычисление средней
        prices = []
        for _, row in df.iterrows():
            price = parse_price(row['url'], row['xpath'])
            if price:
                prices.append(price)
                await update.message.reply_text(f"Цена на {row['title']}: {price}")

        if prices:
            avg_price = sum(prices) / len(prices)
            await update.message.reply_text(f"Средняя цена: {avg_price:.2f}")
        else:
            await update.message.reply_text("Не удалось получить цены.")

    except Exception as e:
        await update.message.reply_text(f"Ошибка при обработке файла: {e}")
    finally:
        os.remove("temp.xlsx")


def main():
    """
    Основная функция
    """
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()


if __name__ == "__main__":
    main()
