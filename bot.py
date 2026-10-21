# ==========================================
# Telegram Bot Template
# aiogram 3.15+
# SQLite + Groq AI
# ==========================================

import asyncio
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from groq import AsyncGroq


# =========================================================
# НАСТРОЙКИ
# =========================================================

# Впишите свои значения прямо сюда — переменные окружения не нужны.
# Замените текстовые примеры на свои настоящие значения.
BOT_TOKEN = os.getenv("API_TOKEN")
GROQ_API_KEY = ""
ADMIN_ID = 275112551  # замените на свой числовой Telegram ID

# Ссылка на канал (кнопка «Наш канал» в главном меню).
CHANNEL_URL = "https://t.me/irinaprokhorchuk"  # замените на ссылку вашего канала

ADMIN_IDS = {ADMIN_ID}


def is_admin(user_id):
    return user_id == ADMIN_ID


AI_PROMPT = (
    "ТЫ — ВИРТУАЛЬНЫЙ ПОМОЩНИК РИЕЛТОРА ИРИНЫ.\n\n"
    "РОЛЬ:\n"
    "Ты представляешь профессионального риелтора Ирину (стаж 11 лет). "
    "Ты — её помощник. Твоя задача: вежливо принять обращение, "
    "зафиксировать данные клиента и передать информацию Ирине.\n\n"
    "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ (СТРОГИЙ ЧЕК-ЛИСТ):\n"
    "Прежде чем давать развёрнутые ответы, ты ОБЯЗАН узнать у пользователя три вещи. "
    "Если клиент не указал их сразу — вежливо задай уточняющие вопросы по одному.\n"
    "1. Вопрос/суть обращения: узнай, какой именно вопрос у клиента "
    "(покупка, продажа, аренда, инвестиции, оценка, конкретный объект).\n"
    "2. Имя: узнай, как зовут клиента.\n"
    "3. Удобное время для ответа: узнай, когда клиенту удобно, "
    "чтобы Ирина (живой человек) с ним связалась.\n\n"
    "Правило: не переходи к глубокой консультации, пока не собраны все три пункта. "
    "Если клиент задаёт вопрос сразу — ответь кратко, но затем обязательно вернись "
    "к сбору данных: «Я обязательно передам ваш вопрос Ирине. Чтобы она подготовилась "
    "и перезвонила вовремя, подскажите, пожалуйста, ваше имя и удобное время для звонка?»\n\n"
    "СТИЛЬ ОБЩЕНИЯ (ЖЁСТКИЕ ПРАВИЛА):\n"
    "- Максимальная вежливость: используй «Здравствуйте», «Пожалуйста», «Благодарю», «Будьте добры». "
    "Избегай фамильярности, сленга и резких фраз.\n"
    "- Эмпатия: показывай, что слышишь клиента "
    "(«Я понимаю, это важный вопрос», «Спасибо, что уточнили»).\n"
    "- Грамотность: пиши чистым русским языком, без ошибок, с правильной пунктуацией.\n"
    "- Лаконичность: не пиши «простыни» текста. Разбивай информацию на короткие абзацы. "
    "Задавай вопросы, чтобы вовлечь в диалог.\n"
    "- Никакого давления: не навязывай услуги, а предлагай помощь.\n\n"
    "ТВОИ ВОЗМОЖНОСТИ И ДОСТУПЫ:\n"
    "Ты имеешь доступ к базе знаний и можешь предоставлять следующую информацию:\n"
    "- Объекты недвижимости: актуальные базы объектов (квартиры, дома, коммерция). "
    "Можешь рассказать о характеристиках, ценах и расположении (в рамках предоставленных данных).\n"
    "- Услуги: консультации, подбор, оценка, сопровождение сделок и другие услуги риелтора.\n"
    "- Информация: можешь проконсультировать по общим вопросам рынка недвижимости, "
    "документам и процедурам.\n\n"
    "АЛГОРИТМ ДЕЙСТВИЙ (ПОШАГОВО):\n"
    "1. Приветствие: поздоровайся, представься помощником риелтора Ирины.\n"
    "2. Выявление потребности: задай вопрос «Чем я могу вам помочь?» "
    "или «Подбираете объект или хотите продать?».\n"
    "3. Сбор данных (чек-лист): если клиент не назвал имя/время/суть — уточни.\n"
    "4. Консультация (опционально): если клиент спрашивает про услуги или объекты — "
    "дай краткую справку, используя свои данные.\n"
    "5. Фиксация: подтверди, что данные записаны. Скажи: "
    "«Ирина свяжется с вами в [указанное время] по вопросу [суть вопроса]».\n"
    "6. Прощание: поблагодари за обращение и пожелай хорошего дня.\n\n"
    "ЗАПРЕТЫ (ЧТО НЕЛЬЗЯ ДЕЛАТЬ):\n"
    "- Не грубить, не перебивать, не использовать капслок.\n"
    "- Не выдумывать несуществующие объекты или цены "
    "(если данных нет в базе — скажи, что Ирина уточнит эту информацию).\n"
    "- Не давать юридических гарантий от своего лица (всегда ссылайся на опыт Ирины).\n"
    "- Не заканчивать диалог, пока не собраны все три обязательных пункта.\n\n"
    "ПРАВИЛА СБОРА ВРЕМЕНИ:\n"
    "- Спрашивай вопросы строго по очереди: сначала суть обращения, потом имя, "
    "потом удобное время.\n"
    "- Не говори про Ирину и её стаж, если тебя об этом не спрашивают.\n"
    "- Если клиент называет время расплывчато — «когда Ирина освободится», "
    "«как получится», «по возможности», «в любое время», «когда удобно», "
    "«на связи», «перезвоните сами» и любые похожие формулировки — "
    "принимай это как полноценный ответ. НЕ переспрашивай точное время "
    "и НЕ проси указать конкретные часы.\n"
    "- Записывай время ровно так, как его назвал клиент, без исправлений и уточнений.\n"
    "- Отвечай вежливо, но максимально коротко. Не пиши длинных сообщений."
)

PHOTO_MAIN = "AgACAgIAAxkBAAMFatT7IL1YE0GPNlY0Krp9X_ZCe4sAAtEkaxtzialKrE7zStz1CPQBAAMCAAN5AAM9BA"
WELCOME_TEXT = "Здравствуйте!\n\nЯ ассистент Ирины: на связи, пока она занята, и готов помочь вам прямо сейчас."

PHOTO_INFO = "AgACAgIAAxkBAAMDatT7HOcJLy_ojQpTXlDnu5G-7OIAAtAkaxtzialKiX9Xwhor8EkBAAMCAAN5AAM9BA"
INFO_TEXT = (
    "Ирина Прохорчук\n"
    "Премиальная недвижимость Санкт-Петербурга\n\n"
    "Недвижимость для меня это пространство для жизни, бизнеса и инвестиций. Более 11 лет помогаю выгодно продавать и покупать объекты в Санкт-Петербурге и Ленобласти.\n\n"
    "Специализация:\n"
    "• Элитная и премиальная недвижимость в городе и пригородах.\n"
    "• Инвестиционные объекты и активы для быстрой реализации.\n"
    "• Аукционный метод продажи: первооткрыватель технологии в Санкт-Петербурге.\n\n"
    "Что делаю:\n"
    "• Продажа в срок: объект продается за 14-21 день, цена на 15-25% выше, чем самостоятельно или с риелторами.\n"
    "• Решаю сложные задачи: вывожу из застоя, сделки на нестабильном рынке, предпродажная подготовка и маркетинг.\n"
    "• Полное сопровождение: юристы, аудит и переговоры при продаже, покупке и выкупе.\n\n"
    "Достижения:\n"
    "• Лауреат премии «КАИССА» за инновации на рынке недвижимости.\n"
    "• Автор книг «Антибедность» и «Делай и богатей».\n\n"
    "Сама формирую спрос на ваш объект. Если цените время и хотите прогнозируемый результат, напишите мне."
)
DATA_FOLDER = "/app/data"
if not os.path.isdir(DATA_FOLDER):
    DATA_FOLDER = "."

DB_PATH = os.path.join(DATA_FOLDER, "bot.db")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан.")

AI_BLOCK_SIZE = 15
AI_WAIT_MINUTES = 10
AI_MAX_BLOCKS = 3


# =========================================================
# BOT
# =========================================================

class CleanChatBot(Bot):
    """Удаляет предыдущее сообщение бота в пользовательском чате."""

    _last_bot_messages = {}

    async def _delete_previous(self, chat_id):
        if chat_id in ADMIN_IDS:
            return
        previous_id = self._last_bot_messages.get(chat_id)
        if not previous_id:
            return
        try:
            await super().delete_message(chat_id=chat_id, message_id=previous_id)
        except Exception:
            pass
        self._last_bot_messages.pop(chat_id, None)

    def _remember(self, chat_id, message_id):
        if chat_id not in ADMIN_IDS:
            self._last_bot_messages[chat_id] = message_id

    async def send_message(self, chat_id, text, **kwargs):
        await self._delete_previous(chat_id)
        result = await super().send_message(chat_id=chat_id, text=text, **kwargs)
        self._remember(chat_id, result.message_id)
        return result

    async def send_photo(self, chat_id, photo, **kwargs):
        await self._delete_previous(chat_id)
        result = await super().send_photo(chat_id=chat_id, photo=photo, **kwargs)
        self._remember(chat_id, result.message_id)
        return result


bot = CleanChatBot(token=BOT_TOKEN)
dp = Dispatcher()


async def safe_edit_text(message, text, reply_markup=None, parse_mode=None):
    """Редактирует текст; если сообщение содержит фото, заменяет его новым."""
    kwargs = {"reply_markup": reply_markup}
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
    try:
        return await message.edit_text(text, **kwargs)
    except TelegramBadRequest as error:
        if "there is no text in the message to edit" not in str(error).lower():
            raise
        try:
            await message.delete()
        except Exception:
            pass
        return await message.answer(text, **kwargs)


groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# =========================================================
# FSM
# =========================================================

class BookingState(StatesGroup):
    waiting_ai = State()


class ObjectAddState(StatesGroup):
    text = State()
    photo = State()


class ObjectEditState(StatesGroup):
    text = State()
    photo = State()


class ServiceAddState(StatesGroup):
    text = State()
    photo = State()


class ServiceEditState(StatesGroup):
    text = State()
    photo = State()


class FileIdState(StatesGroup):
    photo = State()


class BroadcastState(StatesGroup):
    message = State()
    add_button = State()
    button_text = State()
    button_url = State()
    button_style = State()


# =========================================================
# DATABASE
# =========================================================

def db():
    os.makedirs(DATA_FOLDER, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def column_names(connection, table_name: str):
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def ensure_column(connection, table_name: str, column_name: str, definition: str):
    if column_name not in column_names(connection, table_name):
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _migrate_products_to_objects(connection):
    products_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='products'"
    ).fetchone()
    objects_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='objects'"
    ).fetchone()
    if products_exists and not objects_exists:
        try:
            connection.execute("ALTER TABLE products RENAME TO objects")
        except sqlite3.OperationalError:
            pass


def _normalize_objects_table(connection):
    _migrate_products_to_objects(connection)
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='objects'"
    ).fetchone()
    if not exists:
        connection.execute("""
            CREATE TABLE objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                photo_file_id TEXT NOT NULL DEFAULT ''
            )
        """)
        return

    columns = column_names(connection, "objects")
    legacy = {"name", "price", "description"} & columns
    if not legacy:
        ensure_column(connection, "objects", "text", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "objects", "photo_file_id", "TEXT NOT NULL DEFAULT ''")
        return

    rows = connection.execute("SELECT * FROM objects ORDER BY id").fetchall()
    old_columns = [row[1] for row in connection.execute("PRAGMA table_info(objects)").fetchall()]
    index = {name: i for i, name in enumerate(old_columns)}

    def value(row, name, default=""):
        i = index.get(name)
        return row[i] if i is not None and row[i] is not None else default

    connection.execute("DROP TABLE IF EXISTS objects_new")
    connection.execute("""
        CREATE TABLE objects_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            photo_file_id TEXT NOT NULL DEFAULT ''
        )
    """)
    for row in rows:
        text_value = value(row, "text", "").strip()
        if not text_value:
            parts = []
            name = value(row, "name", "").strip()
            price = value(row, "price", "").strip()
            description = value(row, "description", "").strip()
            if name:
                parts.append(name)
            if price:
                parts.append(f"Цена: {price}")
            if description:
                parts.append(description)
            text_value = "\n".join(parts) or "Без названия"
        photo = value(row, "photo_file_id", "") or value(row, "photo", "")
        connection.execute(
            "INSERT INTO objects_new (id, text, photo_file_id) VALUES (?, ?, ?)",
            (value(row, "id", None), text_value, photo),
        )
    connection.execute("DROP TABLE objects")
    connection.execute("ALTER TABLE objects_new RENAME TO objects")


def _migrate_promotions_to_services(connection):
    promotions_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='promotions'"
    ).fetchone()
    services_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='services'"
    ).fetchone()
    if promotions_exists and not services_exists:
        try:
            connection.execute("ALTER TABLE promotions RENAME TO services")
        except sqlite3.OperationalError:
            pass


def _normalize_services_table(connection):
    _migrate_promotions_to_services(connection)
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='services'"
    ).fetchone()
    if not exists:
        connection.execute("""
            CREATE TABLE services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                photo_file_id TEXT NOT NULL DEFAULT ''
            )
        """)
        return

    columns = column_names(connection, "services")
    legacy = {"name", "description"} & columns
    if not legacy:
        ensure_column(connection, "services", "text", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "services", "photo_file_id", "TEXT NOT NULL DEFAULT ''")
        return

    rows = connection.execute("SELECT * FROM services ORDER BY id").fetchall()
    old_columns = [row[1] for row in connection.execute("PRAGMA table_info(services)").fetchall()]
    index = {name: i for i, name in enumerate(old_columns)}

    def value(row, name, default=""):
        i = index.get(name)
        return row[i] if i is not None and row[i] is not None else default

    connection.execute("DROP TABLE IF EXISTS services_new")
    connection.execute("""
        CREATE TABLE services_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            photo_file_id TEXT NOT NULL DEFAULT ''
        )
    """)
    for row in rows:
        text_value = value(row, "text", "").strip()
        if not text_value:
            parts = []
            name = value(row, "name", "").strip()
            description = value(row, "description", "").strip()
            if name:
                parts.append(name)
            if description:
                parts.append(description)
            text_value = "\n".join(parts) or "Без названия"
        photo = value(row, "photo_file_id", "") or value(row, "photo", "")
        connection.execute(
            "INSERT INTO services_new (id, text, photo_file_id) VALUES (?, ?, ?)",
            (value(row, "id", None), text_value, photo),
        )
    connection.execute("DROP TABLE services")
    connection.execute("ALTER TABLE services_new RENAME TO services")


def init_db():
    connection = db()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)
        ensure_column(connection, "users", "username", "TEXT")
        ensure_column(connection, "users", "first_name", "TEXT")
        ensure_column(connection, "users", "is_active", "INTEGER NOT NULL DEFAULT 1")

        _normalize_objects_table(connection)
        _normalize_services_table(connection)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                user_id INTEGER PRIMARY KEY,
                messages_json TEXT NOT NULL DEFAULT '[]',
                ai_answers INTEGER NOT NULL DEFAULT 0,
                block_number INTEGER NOT NULL DEFAULT 1,
                available_at TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        ensure_column(connection, "conversations", "messages_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(connection, "conversations", "ai_answers", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(connection, "conversations", "block_number", "INTEGER NOT NULL DEFAULT 1")
        ensure_column(connection, "conversations", "available_at", "TEXT")
        ensure_column(connection, "conversations", "updated_at", "TEXT NOT NULL DEFAULT ''")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                message_id INTEGER,
                buttons_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)
        ensure_column(connection, "broadcasts", "text", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "broadcasts", "photo_file_id", "TEXT NOT NULL DEFAULT ''")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# =========================================================
# USERS
# =========================================================

def save_user(message: Message):
    connection = db()
    connection.execute("""
        INSERT INTO users (id, username, first_name, is_active)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            is_active = 1
    """, (message.from_user.id, message.from_user.username, message.from_user.first_name))
    connection.commit()
    connection.close()


def deactivate_user(user_id: int):
    connection = db()
    connection.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    connection.commit()
    connection.close()


def get_all_user_ids():
    connection = db()
    rows = connection.execute("SELECT id FROM users WHERE is_active = 1").fetchall()
    connection.close()
    return [row[0] for row in rows]


# =========================================================
# OBJECTS
# =========================================================

def add_object(text: str, photo_file_id: str):
    connection = db()
    connection.execute("INSERT INTO objects (text, photo_file_id) VALUES (?, ?)", (text, photo_file_id))
    connection.commit()
    connection.close()


def get_objects():
    connection = db()
    rows = connection.execute("SELECT id, text, photo_file_id FROM objects ORDER BY id DESC").fetchall()
    connection.close()
    return rows


def get_object(object_id: int):
    connection = db()
    row = connection.execute(
        "SELECT id, text, photo_file_id FROM objects WHERE id = ?", (object_id,)
    ).fetchone()
    connection.close()
    return row


def update_object(object_id: int, text: str, photo_file_id: str):
    connection = db()
    connection.execute(
        "UPDATE objects SET text = ?, photo_file_id = ? WHERE id = ?",
        (text, photo_file_id, object_id),
    )
    connection.commit()
    connection.close()


def delete_object(object_id: int):
    connection = db()
    connection.execute("DELETE FROM objects WHERE id = ?", (object_id,))
    connection.commit()
    connection.close()


# =========================================================
# SERVICES
# =========================================================

def add_service(text: str, photo_file_id: str):
    connection = db()
    connection.execute("INSERT INTO services (text, photo_file_id) VALUES (?, ?)", (text, photo_file_id))
    connection.commit()
    connection.close()


def get_services():
    connection = db()
    rows = connection.execute("SELECT id, text, photo_file_id FROM services ORDER BY id DESC").fetchall()
    connection.close()
    return rows


def get_service(service_id: int):
    connection = db()
    row = connection.execute(
        "SELECT id, text, photo_file_id FROM services WHERE id = ?", (service_id,)
    ).fetchone()
    connection.close()
    return row


def update_service(service_id: int, text: str, photo_file_id: str):
    connection = db()
    connection.execute(
        "UPDATE services SET text = ?, photo_file_id = ? WHERE id = ?",
        (text, photo_file_id, service_id),
    )
    connection.commit()
    connection.close()


def delete_service(service_id: int):
    connection = db()
    connection.execute("DELETE FROM services WHERE id = ?", (service_id,))
    connection.commit()
    connection.close()


# =========================================================
# CONVERSATIONS
# =========================================================

def now_utc():
    return datetime.now(timezone.utc)


def iso_now():
    return now_utc().isoformat()


def get_conversation(user_id: int):
    connection = db()
    row = connection.execute("""
        SELECT messages_json, ai_answers, block_number, available_at
        FROM conversations WHERE user_id = ?
    """, (user_id,)).fetchone()
    connection.close()
    if not row:
        return {"messages": [], "ai_answers": 0, "block_number": 1, "available_at": None}
    try:
        messages = json.loads(row[0])
    except Exception:
        messages = []
    return {
        "messages": messages,
        "ai_answers": int(row[1] or 0),
        "block_number": int(row[2] or 1),
        "available_at": row[3],
    }


def save_conversation(user_id: int, messages: list, ai_answers: int,
                      block_number: int, available_at: Optional[str]):
    connection = db()
    connection.execute("""
        INSERT INTO conversations
            (user_id, messages_json, ai_answers, block_number, available_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            messages_json = excluded.messages_json,
            ai_answers = excluded.ai_answers,
            block_number = excluded.block_number,
            available_at = excluded.available_at,
            updated_at = excluded.updated_at
    """, (user_id, json.dumps(messages, ensure_ascii=False), ai_answers,
          block_number, available_at, iso_now()))
    connection.commit()
    connection.close()


def clear_conversation(user_id: int):
    connection = db()
    connection.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    connection.commit()
    connection.close()


# =========================================================
# SAFE PHOTO SENDING
# =========================================================

async def safe_answer_photo(message: Message, photo_id: str, caption: str, reply_markup=None):
    photo_id = (photo_id or "").strip()
    if photo_id:
        try:
            return await message.answer_photo(
                photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=reply_markup
            )
        except TelegramBadRequest as error:
            logging.warning("Не удалось отправить фото. FILE_ID=%r ERROR=%s", photo_id, error)
        except Exception as error:
            logging.exception("Неожиданная ошибка отправки фото: %s", error)
    return await message.answer(caption, parse_mode="HTML", reply_markup=reply_markup)


async def safe_edit_or_send_photo(callback: CallbackQuery, photo_id: str, caption: str, reply_markup=None):
    photo_id = (photo_id or "").strip()
    if photo_id:
        try:
            new_message = await callback.message.answer_photo(
                photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=reply_markup
            )
            try:
                await callback.message.delete()
            except Exception:
                pass
            return new_message
        except TelegramBadRequest as error:
            logging.warning("Неверный FILE_ID. Использую текстовый вариант. %s", error)
        except Exception as error:
            logging.exception("Ошибка фото. Использую текстовый вариант: %s", error)
    try:
        await safe_edit_text(callback.message, caption, parse_mode="HTML", reply_markup=reply_markup)
        return callback.message
    except Exception:
        return await callback.message.answer(caption, parse_mode="HTML", reply_markup=reply_markup)


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить заявку", callback_data="booking", style="success")],
        [InlineKeyboardButton(text="Информация", callback_data="info", style="primary")],
        [InlineKeyboardButton(text="Объекты", callback_data="objects", style="success")],
        [InlineKeyboardButton(text="Услуги", callback_data="services", style="primary")],
        [InlineKeyboardButton(text="Мой канал", url=CHANNEL_URL, style="success")],
    ])


def back_keyboard(callback_data="back"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=callback_data, style="danger")]
    ])


def role_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Покупатель", callback_data="role_buyer", style="primary")],
        [InlineKeyboardButton(text="Продавец", callback_data="role_seller", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="back", style="danger")],
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Объекты", callback_data="admin_objects", style="success")],
        [InlineKeyboardButton(text="Услуги", callback_data="admin_services", style="primary")],
        [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast", style="primary")],
        [InlineKeyboardButton(text="Получить file_id фото", callback_data="file_id_tool", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_back", style="danger")],
    ])


def object_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить объект", callback_data="object_add", style="success")],
        [InlineKeyboardButton(text="Список объектов", callback_data="object_list", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="admin", style="danger")],
    ])


def service_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить услугу", callback_data="service_add", style="success")],
        [InlineKeyboardButton(text="Список услуг", callback_data="service_list", style="primary")],
        [InlineKeyboardButton(text="Назад", callback_data="admin", style="danger")],
    ])


def cancel_keyboard(callback_data):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=callback_data, style="danger")]
    ])


def confirm_delete_keyboard(kind: str, item_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"confirm_delete_{kind}:{item_id}", style="success")],
        [InlineKeyboardButton(text="Нет", callback_data=f"{kind}_list", style="danger")],
    ])


def booking_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить заявку", callback_data="booking_confirm", style="success")],
        [InlineKeyboardButton(text="Отменить", callback_data="booking_cancel", style="danger")],
    ])


# =========================================================
# AI
# =========================================================

def get_ai_objects_context() -> str:
    rows = get_objects()
    if not rows:
        return (
            "АКТУАЛЬНЫЙ СПИСОК ОБЪЕКТОВ:\n"
            "Объектов пока нет. Не придумывай объекты, цены, характеристики "
            "или наличие, которых нет в этом списке."
        )
    parts = [
        "АКТУАЛЬНЫЙ СПИСОК ОБЪЕКТОВ ИЗ БАЗЫ БОТА:",
        "Используй этот список, когда пользователь спрашивает об объектах. "
        "Отвечай только по данным из него и не придумывай отсутствующие "
        "цены, характеристики, наличие или условия.",
    ]
    for number, (object_id, text, _photo_file_id) in enumerate(rows, start=1):
        parts.append(f"\nОбъект {number} (ID {object_id}):\n{text.strip()}")
    return "\n".join(parts)


def get_ai_services_context() -> str:
    rows = get_services()
    if not rows:
        return (
            "АКТУАЛЬНЫЙ СПИСОК УСЛУГ:\n"
            "Услуг пока нет. Не придумывай услуги, сроки или условия, "
            "которых нет в этом списке."
        )
    parts = [
        "АКТУАЛЬНЫЙ СПИСОК УСЛУГ ИЗ БАЗЫ БОТА:",
        "Используй этот список, когда пользователь спрашивает об услугах. "
        "Не придумывай отсутствующие сроки или условия.",
    ]
    for number, (service_id, text, _photo_file_id) in enumerate(rows, start=1):
        parts.append(f"\nУслуга {number} (ID {service_id}):\n{text.strip()}")
    return "\n".join(parts)


def get_ai_catalog_context() -> str:
    return get_ai_objects_context() + "\n\n" + get_ai_services_context()


def clean_plain_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("**", "").replace("__", "")
    text = text.replace("###", "").replace("##", "").replace("#", "")
    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"^(?:[-*•]+)\s*", "", line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def get_booking_rules_context() -> str:
    return """
ПРАВИЛА ЗАВЕРШЕНИЯ ЗАПИСИ:

1. В основном AI_PROMPT может быть раздел «Обязательные параметры».
2. Если такой раздел есть, используй именно перечисленные там параметры как обязательные.
3. Нужно определить по ВСЕМУ диалогу, какие параметры пользователь уже сообщил.
4. Не считай параметр известным, если пользователь дал слишком расплывчатый ответ. При необходимости задай уточняющий вопрос.
5. Если в AI_PROMPT нет раздела «Обязательные параметры», используй стандартный список:
   - Услуга
   - Время
   - Имя человека
   - Дополнительный комментарий
6. Пока хотя бы одного обязательного параметра не хватает, НЕ завершай запись.
7. Когда все обязательные параметры известны и уточнений больше не нужно, дай короткий нормальный ответ пользователю и в самом конце добавь служебную метку [[BOOKING_READY]].
8. Метку [[BOOKING_READY]] пользователь видеть не должен. Не объясняй её и не выводи её отдельно.
"""


async def ask_ai(messages: list) -> Optional[str]:
    if not groq_client:
        return None
    try:
        catalog_context = get_ai_catalog_context()
        booking_rules = get_booking_rules_context()
        system_content = f"{AI_PROMPT}\n\n{booking_rules}\n\n{catalog_context}"
        response = await groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "system", "content": system_content}, *messages],
            temperature=0.7,
            max_tokens=700,
        )
        answer = response.choices[0].message.content
        return answer.strip() if answer else None
    except Exception as error:
        logging.exception("AI error: %s", error)
        return None


# =========================================================
# BOOKING / AI AGENT
# =========================================================

async def process_ai_message(message: Message):
    user_id = message.from_user.id
    conversation = get_conversation(user_id)
    available_at = conversation.get("available_at")
    if available_at:
        try:
            available_time = datetime.fromisoformat(available_at)
            if now_utc() < available_time:
                remaining = available_time - now_utc()
                minutes = max(1, int(remaining.total_seconds() // 60) + 1)
                await message.answer(f"Следующий блок ответов будет доступен примерно через {minutes} мин.")
                return
            conversation["available_at"] = None
            conversation["ai_answers"] = 0
            conversation["block_number"] += 1
        except Exception:
            conversation["available_at"] = None

    if conversation["block_number"] > AI_MAX_BLOCKS:
        await message.answer("Вы точно готовы оставить заявку?", reply_markup=booking_confirm_keyboard())
        return

    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Пожалуйста, отправьте сообщение текстом.")
        return

    conversation["messages"].append({"role": "user", "content": text})
    answer = await ask_ai(conversation["messages"])
    if not answer:
        conversation["messages"].pop()
        await message.answer("Сейчас не удалось получить ответ AI. Попробуйте ещё раз.")
        return

    booking_ready = "[[BOOKING_READY]]" in answer
    answer = answer.replace("[[BOOKING_READY]]", "").strip()
    answer = clean_plain_text(answer)
    conversation["messages"].append({"role": "assistant", "content": answer})
    conversation["ai_answers"] += 1

    if booking_ready:
        save_conversation(user_id, conversation["messages"], conversation["ai_answers"],
                          conversation["block_number"], conversation["available_at"])
        if answer:
            await message.answer(answer)
        await message.answer("Подтвердить заявку?", reply_markup=booking_confirm_keyboard())
        return

    if conversation["ai_answers"] >= AI_BLOCK_SIZE:
        if conversation["block_number"] >= AI_MAX_BLOCKS:
            save_conversation(user_id, conversation["messages"], conversation["ai_answers"],
                              conversation["block_number"], None)
            await message.answer(answer)
            await message.answer("Вы точно готовы оставить заявку?", reply_markup=booking_confirm_keyboard())
            return
        available_time = now_utc() + timedelta(minutes=AI_WAIT_MINUTES)
        conversation["available_at"] = available_time.isoformat()
        save_conversation(user_id, conversation["messages"], conversation["ai_answers"],
                          conversation["block_number"], conversation["available_at"])
        await message.answer(answer)
        await message.answer(
            f"Лимит в {AI_BLOCK_SIZE} ответов достигнут. "
            f"Следующий блок будет доступен через {AI_WAIT_MINUTES} минут."
        )
        return

    save_conversation(user_id, conversation["messages"], conversation["ai_answers"],
                      conversation["block_number"], conversation["available_at"])
    await message.answer(answer)


@dp.callback_query(F.data == "booking")
async def booking_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    clear_conversation(callback.from_user.id)
    save_conversation(callback.from_user.id, [], 0, 1, None)
    await state.set_state(BookingState.waiting_ai)
    await callback.message.answer("Добро пожаловать! Введите ваш запрос.")
    await callback.answer()


@dp.callback_query(F.data == "booking_confirm")
async def booking_confirm(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    conversation = get_conversation(user_id)
    if not conversation["messages"]:
        await callback.answer("Диалог не найден.", show_alert=True)
        return

    messages = conversation["messages"]
    username = f"@{callback.from_user.username}" if callback.from_user.username else "без username"
    summary_prompt = """
Проанализируй весь диалог пользователя с AI-помощником.
Сделай короткую понятную запись для администратора.
Не придумывай факты, которых не было в диалоге.

Укажи только то, что относится к заявке:
- услуга;
- время;
- имя человека;
- дополнительный комментарий;
- важные детали и пожелания;
- краткое резюме разговора.

Не используй Markdown, звёздочки, двойные звёздочки, подчёркивания, маркеры списков или декоративные символы.
Пиши обычным текстом, коротко и понятно.
Если какого-то поля в диалоге нет, напиши «не указано».
"""
    summary = await ask_ai([*messages, {"role": "user", "content": summary_prompt}])
    if not summary:
        summary = "\n".join(f"{item['role']}: {item['content']}" for item in messages)
    summary = clean_plain_text(summary)
    admin_text = (
        "Новая заявка\n\n"
        f"Имя: {escape(callback.from_user.full_name)}\n"
        f"Username: {escape(username)}\n"
        f"Telegram ID: <code>{user_id}</code>\n\n"
        f"Резюме:\n{escape(summary)}"
    )
    failed_admins = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception as error:
            failed_admins += 1
            logging.exception("Не удалось отправить заявку админу %s: %s", admin_id, error)

    if failed_admins == len(ADMIN_IDS):
        await callback.answer("Не удалось отправить заявку. Попробуйте ещё раз.", show_alert=True)
        return

    clear_conversation(user_id)
    await state.clear()
    await callback.message.answer(
        "Спасибо! Ваша заявка отправлена. Мы свяжемся с вами в ближайшее время.",
        reply_markup=main_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "booking_cancel")
async def booking_cancel(callback: CallbackQuery, state: FSMContext):
    clear_conversation(callback.from_user.id)
    await state.clear()
    await callback.message.answer("Заявка отменена.", reply_markup=main_keyboard())
    await callback.answer()


# =========================================================
# AI MESSAGES
# =========================================================

@dp.message(BookingState.waiting_ai)
async def ai_active_message(message: Message):
    save_user(message)
    await process_ai_message(message)


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    clear_conversation(message.from_user.id)
    save_user(message)
    await safe_answer_photo(message, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())


# =========================================================
# INFO
# =========================================================

@dp.callback_query(F.data == "info")
async def info_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_or_send_photo(callback, PHOTO_INFO, INFO_TEXT, back_keyboard())
    await callback.answer()


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    clear_conversation(callback.from_user.id)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await safe_answer_photo(callback.message, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())
    await callback.answer()


# =========================================================
# CATALOG NAVIGATION
# =========================================================

def catalog_keyboard(prefix: str, index: int, total: int):
    previous_index = (index - 1) % total
    next_index = (index + 1) % total
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="←", callback_data=f"{prefix}_{previous_index}"),
            InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
            InlineKeyboardButton(text="→", callback_data=f"{prefix}_{next_index}"),
        ],
        [InlineKeyboardButton(text="Назад", callback_data="back", style="danger")],
    ])


async def show_catalog_item(callback: CallbackQuery, items, index: int, prefix: str):
    total = len(items)
    index %= total
    _, text, photo_id = items[index]
    markup = catalog_keyboard(prefix, index, total)
    new_message = await safe_answer_photo(callback.message, photo_id, text or "Без описания.", markup)
    if new_message is not callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
    await callback.answer()


# =========================================================
# OBJECTS - USER
# =========================================================

@dp.callback_query(F.data == "objects")
async def objects_callback(callback: CallbackQuery):
    objects = get_objects()
    if not objects:
        await safe_edit_text(callback.message, "Объекты пока не добавлены.", reply_markup=back_keyboard())
        await callback.answer()
        return
    await show_catalog_item(callback, objects, 0, "object_view")


@dp.callback_query(F.data.startswith("object_view_"))
async def object_view_callback(callback: CallbackQuery):
    objects = get_objects()
    if not objects:
        await safe_edit_text(callback.message, "Объекты пока не добавлены.", reply_markup=back_keyboard())
        await callback.answer()
        return
    try:
        index = int(callback.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка навигации.", show_alert=True)
        return
    await show_catalog_item(callback, objects, index, "object_view")


# =========================================================
# SERVICES - USER
# =========================================================

@dp.callback_query(F.data == "services")
async def services_callback(callback: CallbackQuery):
    services = get_services()
    if not services:
        await safe_edit_text(callback.message, "Услуги пока не добавлены.", reply_markup=back_keyboard())
        await callback.answer()
        return
    await show_catalog_item(callback, services, 0, "service_view")


@dp.callback_query(F.data.startswith("service_view_"))
async def service_view_callback(callback: CallbackQuery):
    services = get_services()
    if not services:
        await safe_edit_text(callback.message, "Услуги пока не добавлены.", reply_markup=back_keyboard())
        await callback.answer()
        return
    try:
        index = int(callback.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка навигации.", show_alert=True)
        return
    await show_catalog_item(callback, services, index, "service_view")


# =========================================================
# ADMIN
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await state.clear()
    await message.answer("Админ-панель", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "admin")
async def admin_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await safe_edit_text(callback.message, "Админ-панель", reply_markup=admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "file_id_tool")
async def file_id_tool(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await state.set_state(FileIdState.photo)
    await safe_edit_text(
        callback.message,
        "Отправьте фотографию.\n\nЯ пришлю её Telegram file_id, который можно использовать в коде бота.",
        reply_markup=cancel_keyboard("admin"),
    )
    await callback.answer()


@dp.message(FileIdState.photo)
async def file_id_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.photo:
        await message.answer("Отправьте именно фотографию.")
        return
    photo_id = message.photo[-1].file_id
    await state.clear()
    await message.answer(f"file_id фото:\n\n{photo_id}", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await safe_answer_photo(callback.message, PHOTO_MAIN, WELCOME_TEXT, main_keyboard())
    await callback.answer()


# =========================================================
# ADMIN OBJECTS
# =========================================================

@dp.callback_query(F.data == "admin_objects")
async def admin_objects(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await safe_edit_text(callback.message, "Управление объектами", reply_markup=object_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "object_add")
async def object_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await state.set_state(ObjectAddState.text)
    await safe_edit_text(
        callback.message,
        "Отправьте объект одним сообщением.\n\nМожно отправить обычный текст или фотографию с подписью.\nФотография автоматически сохранится как Telegram file_id.",
        reply_markup=cancel_keyboard("admin_objects"),
    )
    await callback.answer()


@dp.message(ObjectAddState.text)
async def object_add_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = (message.caption or "").strip()
    else:
        photo_id = ""
        text = (message.text or "").strip()
    if not text and not photo_id:
        await message.answer("Отправьте текст объекта или фотографию с подписью.")
        return
    add_object(text, photo_id)
    await state.clear()
    result_text = "Объект добавлен."
    if photo_id:
        result_text += f"\n\nfile_id фото:\n{photo_id}"
    await message.answer(result_text, reply_markup=object_admin_keyboard())


@dp.callback_query(F.data == "object_list")
async def object_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    objects = get_objects()
    if not objects:
        await safe_edit_text(callback.message, "Объектов пока нет.", reply_markup=object_admin_keyboard())
        await callback.answer()
        return
    await safe_edit_text(callback.message, "Список объектов")
    for object_id, text, photo_id in objects:
        await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Изменить", callback_data=f"edit_object:{object_id}", style="primary")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_object:{object_id}", style="danger")],
        ]))
    await callback.message.answer("Управление объектами", reply_markup=object_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_object:"))
async def edit_object(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    object_id = int(callback.data.split(":")[1])
    object_row = get_object(object_id)
    if not object_row:
        await callback.answer("Объект не найден.", show_alert=True)
        return
    await state.clear()
    await state.update_data(object_id=object_id)
    await state.set_state(ObjectEditState.text)
    await safe_edit_text(callback.message, "Отправьте новый полный текст объекта.",
                         reply_markup=cancel_keyboard("object_list"))
    await callback.answer()


@dp.message(ObjectEditState.text)
async def object_edit_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Отправьте полный текст объекта.")
        return
    await state.update_data(text=text)
    await state.set_state(ObjectEditState.photo)
    await message.answer(
        "Отправьте новую фотографию объекта.\n\nЕсли нужно оставить старое фото, напишите «Оставить».\nЕсли фото нужно убрать, напишите «Без фото»."
    )


@dp.message(ObjectEditState.photo)
async def object_edit_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    old_object = get_object(data["object_id"])
    if not old_object:
        await state.clear()
        await message.answer("Объект не найден.", reply_markup=object_admin_keyboard())
        return
    if message.photo:
        photo_id = message.photo[-1].file_id
    else:
        command = (message.text or "").strip().lower()
        if command == "оставить":
            photo_id = old_object[2]
        elif command == "без фото":
            photo_id = ""
        else:
            await message.answer("Отправьте фотографию, «Оставить» или «Без фото».")
            return
    update_object(data["object_id"], data["text"], photo_id)
    await state.clear()
    await message.answer("Объект обновлён.", reply_markup=object_admin_keyboard())


@dp.callback_query(F.data.startswith("delete_object:"))
async def delete_object_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    object_id = int(callback.data.split(":")[1])
    await safe_edit_text(callback.message, "Удалить этот объект?",
                         reply_markup=confirm_delete_keyboard("object", object_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete_object:"))
async def delete_object_final(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    object_id = int(callback.data.split(":")[1])
    delete_object(object_id)
    await safe_edit_text(callback.message, "Объект удалён.", reply_markup=object_admin_keyboard())
    await callback.answer()


# =========================================================
# ADMIN SERVICES
# =========================================================

@dp.callback_query(F.data == "admin_services")
async def admin_services(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await safe_edit_text(callback.message, "Управление услугами", reply_markup=service_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "service_add")
async def service_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await state.set_state(ServiceAddState.text)
    await safe_edit_text(
        callback.message,
        "Отправьте услугу одним сообщением.\n\nМожно отправить обычный текст или фотографию с подписью.\nФотография автоматически сохранится как Telegram file_id.",
        reply_markup=cancel_keyboard("admin_services"),
    )
    await callback.answer()


@dp.message(ServiceAddState.text)
async def service_add_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = (message.caption or "").strip()
    else:
        photo_id = ""
        text = (message.text or "").strip()
    if not text and not photo_id:
        await message.answer("Отправьте текст услуги или фотографию с подписью.")
        return
    add_service(text, photo_id)
    await state.clear()
    result_text = "Услуга добавлена."
    if photo_id:
        result_text += f"\n\nfile_id фото:\n{photo_id}"
    await message.answer(result_text, reply_markup=service_admin_keyboard())


@dp.callback_query(F.data == "service_list")
async def service_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    services = get_services()
    if not services:
        await safe_edit_text(callback.message, "Услуг пока нет.", reply_markup=service_admin_keyboard())
        await callback.answer()
        return
    await safe_edit_text(callback.message, "Список услуг")
    for service_id, text, photo_id in services:
        await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Изменить", callback_data=f"edit_service:{service_id}", style="primary")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_service:{service_id}", style="danger")],
        ]))
    await callback.message.answer("Управление услугами", reply_markup=service_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_service:"))
async def edit_service(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    service_id = int(callback.data.split(":")[1])
    service = get_service(service_id)
    if not service:
        await callback.answer("Услуга не найдена.", show_alert=True)
        return
    await state.clear()
    await state.update_data(service_id=service_id)
    await state.set_state(ServiceEditState.text)
    await safe_edit_text(callback.message, "Отправьте новый полный текст услуги.",
                         reply_markup=cancel_keyboard("service_list"))
    await callback.answer()


@dp.message(ServiceEditState.text)
async def service_edit_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Отправьте полный текст услуги.")
        return
    await state.update_data(text=text)
    await state.set_state(ServiceEditState.photo)
    await message.answer(
        "Отправьте новую фотографию услуги.\n\nЕсли нужно оставить старое фото, напишите «Оставить».\nЕсли фото нужно убрать, напишите «Без фото»."
    )


@dp.message(ServiceEditState.photo)
async def service_edit_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    old_service = get_service(data["service_id"])
    if not old_service:
        await state.clear()
        await message.answer("Услуга не найдена.", reply_markup=service_admin_keyboard())
        return
    if message.photo:
        photo_id = message.photo[-1].file_id
    else:
        command = (message.text or "").strip().lower()
        if command == "оставить":
            photo_id = old_service[2]
        elif command == "без фото":
            photo_id = ""
        else:
            await message.answer("Отправьте фотографию, «Оставить» или «Без фото».")
            return
    update_service(data["service_id"], data["text"], photo_id)
    await state.clear()
    await message.answer("Услуга обновлена.", reply_markup=service_admin_keyboard())


@dp.callback_query(F.data.startswith("delete_service:"))
async def delete_service_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    service_id = int(callback.data.split(":")[1])
    await safe_edit_text(callback.message, "Удалить эту услугу?",
                         reply_markup=confirm_delete_keyboard("service", service_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_delete_service:"))
async def delete_service_final(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    service_id = int(callback.data.split(":")[1])
    delete_service(service_id)
    await safe_edit_text(callback.message, "Услуга удалена.", reply_markup=service_admin_keyboard())
    await callback.answer()


# =========================================================
# BROADCAST
# =========================================================

def broadcast_button_keyboard(buttons):
    if not buttons:
        return None
    rows = []
    for button in buttons:
        rows.append([InlineKeyboardButton(
            text=button["text"], url=button["url"], style=button.get("style", "primary")
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_controls():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить кнопку", callback_data="broadcast_add_button", style="primary")],
        [InlineKeyboardButton(text="Предпросмотр", callback_data="broadcast_preview", style="primary")],
        [InlineKeyboardButton(text="Отправить", callback_data="broadcast_send", style="success")],
        [InlineKeyboardButton(text="Отмена", callback_data="broadcast_cancel", style="danger")],
    ])


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await state.set_state(BroadcastState.message)
    await safe_edit_text(
        callback.message,
        "Отправьте сообщение для рассылки.\n\nМожно отправить обычный текст или фотографию с подписью.",
        reply_markup=cancel_keyboard("admin"),
    )
    await callback.answer()


@dp.message(BroadcastState.message)
async def broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = (message.caption or "").strip()
    else:
        photo_id = ""
        text = (message.text or "").strip()
    if not text and not photo_id:
        await message.answer("Отправьте текст или фотографию с подписью.")
        return
    await state.update_data(broadcast_text=text, broadcast_photo_file_id=photo_id, broadcast_buttons=[])
    await state.set_state(BroadcastState.add_button)
    if photo_id:
        await message.answer(
            "Фото получено и сохранено как Telegram file_id.\n\nТеперь можно добавить кнопки или отправить рассылку.",
            reply_markup=broadcast_controls(),
        )
    else:
        await message.answer("Сообщение получено.\n\nТеперь можно добавить кнопки или отправить рассылку.",
                             reply_markup=broadcast_controls())


@dp.callback_query(F.data == "broadcast_add_button")
async def broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BroadcastState.button_text)
    await callback.message.answer("Введите название кнопки.")
    await callback.answer()


@dp.message(BroadcastState.button_text)
async def broadcast_button_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите название кнопки.")
        return
    await state.update_data(current_button_text=text)
    await state.set_state(BroadcastState.button_url)
    await message.answer("Отправьте ссылку кнопки.")


@dp.message(BroadcastState.button_url)
async def broadcast_button_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    url = (message.text or "").strip()
    if not (url.startswith("https://") or url.startswith("http://") or url.startswith("tg://")):
        await message.answer("Ссылка должна начинаться с https://, http:// или tg://.")
        return
    await state.update_data(current_button_url=url)
    await state.set_state(BroadcastState.button_style)
    await message.answer("Выберите стиль кнопки.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Синий", callback_data="broadcast_style_primary", style="primary")],
        [InlineKeyboardButton(text="Зелёный", callback_data="broadcast_style_success", style="success")],
        [InlineKeyboardButton(text="Красный", callback_data="broadcast_style_danger", style="danger")],
    ]))


async def finish_broadcast_button(callback: CallbackQuery, state: FSMContext, style: str):
    data = await state.get_data()
    buttons = data.get("broadcast_buttons", [])
    buttons.append({"text": data["current_button_text"], "url": data["current_button_url"], "style": style})
    await state.update_data(broadcast_buttons=buttons)
    await state.set_state(BroadcastState.add_button)
    await callback.message.answer("Кнопка добавлена.", reply_markup=broadcast_controls())
    await callback.answer()


@dp.callback_query(F.data == "broadcast_style_primary")
async def broadcast_style_primary(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await finish_broadcast_button(callback, state, "primary")


@dp.callback_query(F.data == "broadcast_style_success")
async def broadcast_style_success(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await finish_broadcast_button(callback, state, "success")


@dp.callback_query(F.data == "broadcast_style_danger")
async def broadcast_style_danger(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await finish_broadcast_button(callback, state, "danger")


@dp.callback_query(F.data == "broadcast_preview")
async def broadcast_preview(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    photo_id = data.get("broadcast_photo_file_id", "")
    markup = broadcast_button_keyboard(data.get("broadcast_buttons", []))
    try:
        if photo_id:
            await bot.send_photo(chat_id=callback.from_user.id, photo=photo_id, caption=text or None, reply_markup=markup)
        else:
            await bot.send_message(chat_id=callback.from_user.id, text=text, reply_markup=markup)
    except Exception as error:
        logging.exception("Ошибка предпросмотра рассылки: %s", error)
        await callback.message.answer("Не удалось показать предпросмотр. Проверьте фотографию или текст.")
    await callback.answer()


@dp.callback_query(F.data == "broadcast_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    photo_id = data.get("broadcast_photo_file_id", "")
    markup = broadcast_button_keyboard(data.get("broadcast_buttons", []))
    if not text and not photo_id:
        await callback.answer("Сообщение не найдено.", show_alert=True)
        return
    user_ids = get_all_user_ids()
    await callback.message.answer(f"Рассылка началась.\nПолучателей: {len(user_ids)}")
    await callback.answer()
    sent = 0
    failed = 0
    for user_id in user_ids:
        try:
            if photo_id:
                await bot.send_photo(chat_id=user_id, photo=photo_id, caption=text or None, reply_markup=markup)
            else:
                await bot.send_message(chat_id=user_id, text=text, reply_markup=markup)
            sent += 1
        except Exception as error:
            failed += 1
            logging.warning("Рассылка пользователю %s не удалась: %s", user_id, error)
            error_text = str(error).lower()
            if ("blocked" in error_text or "chat not found" in error_text
                    or "user is deactivated" in error_text):
                deactivate_user(user_id)
        await asyncio.sleep(0.05)
    await state.clear()
    await callback.message.answer(
        "Рассылка завершена.\n\n"
        f"Всего: {len(user_ids)}\nДоставлено: {sent}\nНе доставлено: {failed}",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.answer("Рассылка отменена.", reply_markup=admin_keyboard())
    await callback.answer()


# =========================================================
# ORDINARY MESSAGES
# =========================================================

@dp.message()
async def fallback(message: Message):
    save_user(message)
    await message.answer("Используйте кнопки меню.", reply_markup=main_keyboard())


# =========================================================
# GLOBAL ERROR HANDLER
# =========================================================

@dp.errors()
async def global_error_handler(event):
    logging.exception("Unhandled bot error: %s", getattr(event, "exception", event))
    return True


# =========================================================
# STARTUP
# =========================================================

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    init_db()
    logging.info("Bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
