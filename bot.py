import os
import random

import requests
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


load_dotenv(override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
REST_COUNTRIES_BASE = "https://restcountries.com/v3.1"


def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ["🌍 Случайная страна", "ℹ️ Помощь"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def format_country(country: dict) -> tuple[str, str | None]:
    name_data = country.get("name", {})
    common_name = name_data.get("common", "-")
    official_name = name_data.get("official", "-")

    capital = ", ".join(country.get("capital", ["-"]))
    region = country.get("region", "-")
    subregion = country.get("subregion", "-")

    population = country.get("population")
    if isinstance(population, int):
        population_text = f"{population:,}".replace(",", " ")
    else:
        population_text = "-"

    area = country.get("area")
    if isinstance(area, (int, float)):
        area_text = f"{area:,.0f}".replace(",", " ") + " км²"
    else:
        area_text = "-"

    currencies_data = country.get("currencies", {})
    if isinstance(currencies_data, dict) and currencies_data:
        currencies = []
        for currency_code, value in currencies_data.items():
            if isinstance(value, dict):
                currency_name = value.get("name", currency_code)
                currency_symbol = value.get("symbol", "")
                if currency_symbol:
                    currencies.append(f"{currency_name} ({currency_symbol})")
                else:
                    currencies.append(currency_name)
            else:
                currencies.append(currency_code)
        currencies_text = ", ".join(currencies)
    else:
        currencies_text = "-"

    languages_data = country.get("languages", {})
    if isinstance(languages_data, dict) and languages_data:
        languages_text = ", ".join(languages_data.values())
    else:
        languages_text = "-"

    flag_emoji = country.get("flag", "")
    flag_url = country.get("flags", {}).get("png")

    text = (
        f"{flag_emoji} Страна: {common_name}\n"
        f"Официальное название: {official_name}\n"
        f"Столица: {capital}\n"
        f"Регион: {region}\n"
        f"Субрегион: {subregion}\n"
        f"Население: {population_text}\n"
        f"Площадь: {area_text}\n"
        f"Валюты: {currencies_text}\n"
        f"Языки: {languages_text}"
    )

    return text, flag_url


def search_country_by_name(name: str):
    # Ограничиваем fields, чтобы не тянуть лишний JSON.
    params = {
        "fields": "name,capital,region,subregion,population,area,currencies,languages,flags,flag"
    }
    url = f"{REST_COUNTRIES_BASE}/name/{name.strip()}"

    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.RequestException:
        return None, "Не удалось подключиться к API стран. Попробуйте позже."

    if response.status_code == 404:
        return None, "Страна не найдена. Проверьте название."

    if response.status_code != 200:
        return None, f"Ошибка API: {response.status_code}"

    data = response.json()
    if not isinstance(data, list) or not data:
        return None, "Страна не найдена."

    lower_name = name.strip().lower()
    for country in data:
        common = country.get("name", {}).get("common", "").lower()
        official = country.get("name", {}).get("official", "").lower()
        if lower_name == common or lower_name == official:
            return country, None

    return data[0], None


def get_random_country():
    params = {
        "fields": "name,capital,region,subregion,population,area,currencies,languages,flags,flag"
    }
    url = f"{REST_COUNTRIES_BASE}/all"

    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.RequestException:
        return None, "Не удалось подключиться к API стран. Попробуйте позже."

    if response.status_code != 200:
        return None, f"Ошибка API: {response.status_code}"

    data = response.json()
    if not isinstance(data, list) or not data:
        return None, "Список стран пуст."

    return random.choice(data), None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я бот по странам мира.\n"
        "Отправь название страны (например: Japan, Kazakhstan, Germany).\n"
        "Также можно нажать кнопку случайной страны.",
        reply_markup=get_main_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Доступно:\n"
        "/start - старт\n"
        "/help - помощь\n"
        "/random - случайная страна\n"
        "Или просто отправь название страны текстом.",
        reply_markup=get_main_keyboard(),
    )


async def random_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    country, error = get_random_country()
    if error:
        await update.message.reply_text(error, reply_markup=get_main_keyboard())
        return

    text, image_url = format_country(country)
    if image_url:
        await update.message.reply_photo(photo=image_url, caption=text, reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=get_main_keyboard())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None:
        return

    user_text = (message.text or "").strip()
    if not user_text:
        await message.reply_text("Введите название страны.", reply_markup=get_main_keyboard())
        return

    command_like = user_text.lower()
    if command_like in {"ℹ️ помощь", "помощь", "help"}:
        await help_command(update, context)
        return
    if command_like in {"🌍 случайная страна", "случайная страна", "random"}:
        await random_country(update, context)
        return

    country, error = search_country_by_name(user_text)
    if error:
        await message.reply_text(error, reply_markup=get_main_keyboard())
        return

    text, image_url = format_country(country)
    if image_url:
        await message.reply_photo(photo=image_url, caption=text, reply_markup=get_main_keyboard())
    else:
        await message.reply_text(text, reply_markup=get_main_keyboard())


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN в .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("random", random_country))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_text))

    print("Бот запущен. Нажмите Ctrl+C для остановки.")
    app.run_polling()


if __name__ == "__main__":
    main()
