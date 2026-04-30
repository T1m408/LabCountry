import os
import random

import requests
from dotenv import load_dotenv
from telegram import (
    ReplyKeyboardMarkup,
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)


load_dotenv(override=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
REST_COUNTRIES_BASE = "https://restcountries.com/v3.1"
QUIZ_STATE_BY_CHAT = {}


def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ["🌍 Случайная страна", "🏳️ Угадай флаг"],
        ["ℹ️ Помощь"],
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
    params = {
        "fields": "name,capital,region,subregion,population,area,currencies,languages,flags,flag"
    }

    url = f"{REST_COUNTRIES_BASE}/name/{name.strip()}"

    try:
        response = requests.get(url, params=params, timeout=10)
    except requests.RequestException:
        return None, "Не удалось подключиться к API стран."

    if response.status_code == 404:
        return None, "Страна не найдена."

    if response.status_code != 200:
        return None, f"Ошибка API: {response.status_code}"

    data = response.json()

    if not isinstance(data, list) or not data:
        return None, "Страна не найдена."

    return data[0], None


def get_random_country():
    params = {
        "fields": "name,capital,region,subregion,population,area,currencies,languages,flags,flag"
    }

    try:
        response = requests.get(
            f"{REST_COUNTRIES_BASE}/all", params=params, timeout=10)
        data = response.json()
        return random.choice(data), None
    except:
        return None, "Ошибка загрузки стран."


def get_countries_for_quiz():
    params = {
        "fields": "name,flags,flag"
    }

    try:
        response = requests.get(
            f"{REST_COUNTRIES_BASE}/all", params=params, timeout=10)
        data = response.json()
    except:
        return None, "Ошибка загрузки стран."

    valid = []

    for country in data:
        name = country.get("name", {}).get("common")
        flag_url = country.get("flags", {}).get("png")

        if name and flag_url:
            valid.append(country)

    return valid, None


def build_quiz_round(countries: list[dict]):
    correct = random.choice(countries)
    correct_name = correct["name"]["common"]
    flag_url = correct["flags"]["png"]

    other = []

    while len(other) < 3:
        c = random.choice(countries)
        name = c["name"]["common"]

        if name != correct_name and name not in other:
            other.append(name)

    options = other + [correct_name]
    random.shuffle(options)

    return {
        "correct": correct_name,
        "options": options,
        "flag_url": flag_url
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот по странам мира.\n"
        "Напиши название страны или выбери кнопку.",
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - старт\n"
        "/help - помощь\n"
        "/random - случайная страна\n"
        "/quiz - викторина",
        reply_markup=get_main_keyboard()
    )


async def random_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country, error = get_random_country()

    if error:
        await update.message.reply_text(error)
        return

    text, image_url = format_country(country)

    await update.message.reply_photo(
        photo=image_url,
        caption=text,
        reply_markup=get_main_keyboard()
    )


async def quiz_country_flag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    countries, error = get_countries_for_quiz()

    if error:
        await message.reply_text(error)
        return

    round_data = build_quiz_round(countries)

    QUIZ_STATE_BY_CHAT[message.chat_id] = round_data

    buttons = []

    for option in round_data["options"]:
        buttons.append(
            [InlineKeyboardButton(option, callback_data=option)]
        )

    keyboard = InlineKeyboardMarkup(buttons)

    await message.reply_photo(
        photo=round_data["flag_url"],
        caption="🏳️ Угадай страну по флагу:",
        reply_markup=keyboard
    )


async def quiz_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    user_answer = query.data

    round_data = QUIZ_STATE_BY_CHAT.get(chat_id)

    if not round_data:
        await query.edit_message_caption("Викторина устарела.")
        return

    correct = round_data["correct"]

    if user_answer == correct:
        text = f"✅ Верно! Это {correct}"
    else:
        text = f"❌ Неверно.\nПравильный ответ: {correct}"

    QUIZ_STATE_BY_CHAT.pop(chat_id, None)

    await query.edit_message_caption(text)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = (update.message.text or "").strip().lower()

    if "помощ" in user_text:
        await help_command(update, context)
        return

    if "случайная страна" in user_text:
        await random_country(update, context)
        return

    if "угадай флаг" in user_text:
        await quiz_country_flag(update, context)
        return

    country, error = search_country_by_name(user_text)

    if error:
        await update.message.reply_text(error)
        return

    text, image_url = format_country(country)

    await update.message.reply_photo(
        photo=image_url,
        caption=text,
        reply_markup=get_main_keyboard()
    )


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("random", random_country))
    app.add_handler(CommandHandler("quiz", quiz_country_flag))

    app.add_handler(CallbackQueryHandler(quiz_button))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    print("Бот запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()
