import logging
import json
import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Токен вашего второго бота
API_TOKEN = "8850117771:AAHyO8CLOxVxmPRvGOwuz4zfVNBUqCbRoJE"
# Ваш личный ID суперадмина
ADMIN_ID = 901920811

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
DATA_FILE = "simple_bot_tasks.json"


class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()
    waiting_for_bonus_points = State()
    waiting_for_penalty_points = State()
    waiting_for_support_message = State()
    waiting_for_admin_reply = State()


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "history": []}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def init_user(data, user_id, name):
    uid = str(user_id)
    if "users" not in data:
        data["users"] = {}
    if uid not in data["users"]:
        data["users"][uid] = {"name": name, "points": 0.0, "done": 0, "failed": 0}
    else:
        data["users"][uid]["name"] = name


def get_status_text(score):
    if score >= 71:
        return "👑 Продуктивный монстр"
    elif score >= 31:
        return "💪 Красавчик"
    elif score >= 0:
        return "🌱 Новичок"
    else:
        return "⚠️ Ленивая панда"


def get_main_keyboard(user_id):
    builder = ReplyKeyboardBuilder()
    if user_id == ADMIN_ID:
        builder.add(types.KeyboardButton(text="🕵️‍♂️ ПАНЕЛЬ СУПЕРАДМИНА"))

    builder.add(types.KeyboardButton(text="📊 Мой статус и РЕЙТИНГ"))
    builder.add(types.KeyboardButton(text="🔥 Сделал на отлично (+1)"))
    builder.add(types.KeyboardButton(text="💪 Кое-что сделал (+0.5)"))
    builder.add(types.KeyboardButton(text="💩 Забил на задачу (-5)"))
    builder.add(types.KeyboardButton(text="🗑 Отменить моё последнее дело"))
    builder.add(types.KeyboardButton(text="🆘 Написать в поддержку"))

    if user_id == ADMIN_ID:
        builder.adjust(1, 1, 2, 2, 1)
    else:
        builder.adjust(1, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def get_users_inline_keyboard(action_type):
    data = load_data()
    builder = InlineKeyboardBuilder()
    if "users" in data:
        for uid, user in data["users"].items():
            builder.add(types.InlineKeyboardButton(text=user["name"], callback_data=f"{action_type}:{uid}"))
    builder.adjust(1)
    return builder.as_markup()


# --- ФУНКЦИЯ ЕЖЕДНЕВНОГО НАПОМИНАНИЯ ---
async def send_daily_reminder():
    data = load_data()
    if "users" in data and data["users"]:
        for uid in data["users"].keys():
            try:
                await bot.send_message(
                    chat_id=int(uid),
                    text="🔔 **НАПОМИНАНИЕ:**\n\nНе забудь добавить свои дела за сегодня и проверить свой РЕЙТИНГ! 🚀",
                    parse_mode="Markdown"
                )
            except Exception:
                pass


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    data = load_data()
    init_user(data, message.from_user.id, message.from_user.full_name)
    save_data(data)
    await message.answer("👋 Привет! Трекер рейтинга запущен.", reply_markup=get_main_keyboard(message.from_user.id))


@dp.message(F.text == "📊 Мой статус и РЕЙТИНГ")
async def show_status(message: types.Message):
    data = load_data()
    user_id = str(message.from_user.id)
    init_user(data, user_id, message.from_user.full_name)
    user = data["users"][user_id]
    status = get_status_text(user["points"])
    await message.answer(
        f"🏆 **ИНДЕКС ЭФФЕКТИВНОСТИ** 🏆\n\n💰 Мой РЕЙТИНГ: **{user['points']} / 100**\n🚘 Статус: {status}",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


# --- ФУНКЦИОНАЛ ПОДДЕРЖКИ ---
@dp.message(F.text == "🆘 Написать в поддержку")
async def support_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_support_message)
    await message.answer("✍️ Напишите ваше сообщение для поддержки:", reply_markup=types.ReplyKeyboardRemove())


@dp.message(AdminStates.waiting_for_support_message)
async def support_send(message: types.Message, state: FSMContext):
    user_msg = message.text.strip()
    await state.clear()
    reply_menu = InlineKeyboardBuilder().add(
        types.InlineKeyboardButton(text="✍️ Ответить", callback_data=f"reply_user:{message.from_user.id}"))
    await bot.send_message(chat_id=ADMIN_ID,
                           text=f"📬 **ПОДДЕРЖКА!**\n👤 От: {message.from_user.full_name}\n💬 {user_msg}",
                           reply_markup=reply_menu.as_markup())
    await message.answer("✅ Отправлено администратору!", reply_markup=get_main_keyboard(message.from_user.id))


@dp.callback_query(F.data.startswith("reply_user:"))
async def admin_reply_start(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target_uid=callback.data.split(":")[-1])
    await state.set_state(AdminStates.waiting_for_admin_reply)
    await callback.message.answer("✍️ Введите ответ:")
    await callback.answer()


@dp.message(AdminStates.waiting_for_admin_reply)
async def admin_reply_send(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(chat_id=int(user_data.get("target_uid")),
                               text=f"✉️ **ОТВЕТ ОТ ПОДДЕРЖКИ:**\n\n{message.text}")
        await message.answer("✅ Доставлено!", reply_markup=get_main_keyboard(ADMIN_ID))
    except Exception:
        pass


# --- ПАНЕЛЬ СУПЕРАДМИНА ---
@dp.message(F.text == "🕵️‍♂️ ПАНЕЛЬ СУПЕРАДМИНА")
async def show_admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    adm_menu = InlineKeyboardBuilder()
    adm_menu.add(types.InlineKeyboardButton(text="📊 Сводный рейтинг всех", callback_data="adm_view_all"))
    adm_menu.add(types.InlineKeyboardButton(text="📢 Сделать объявление всем", callback_data="adm_broadcast"))
    adm_menu.add(types.InlineKeyboardButton(text="🎁 Начислить бонус", callback_data="adm_bonus"))
    adm_menu.add(types.InlineKeyboardButton(text="🚨 Выписать штраф", callback_data="adm_penalty"))
    adm_menu.add(
        types.InlineKeyboardButton(text="🗑 Отменить последнее дело у кого-то", callback_data="adm_cancel_user"))
    adm_menu.add(types.InlineKeyboardButton(text="🧹 Обнулить весь рейтинг", callback_data="adm_clear_all"))
    adm_menu.adjust(1)
    await message.answer("🔒 **ГЛАВНЫЙ ПУЛЬТ УПРАВЛЕНИЯ СУПЕРАДМИНА:**", reply_markup=adm_menu.as_markup())


@dp.callback_query(F.data == "adm_view_all")
async def admin_view_all(callback: types.CallbackQuery):
    data = load_data()
    users_text = "📊 **СКРЫТЫЙ СЕМЕЙНЫЙ РЕЙТИНГ:**\n\n"
    for uid, user in data.get("users", {}).items():
        users_text += f"👤 **{user['name']}**: РЕЙТИНГ **{user['points']} б.**\n"
    await callback.message.answer(users_text)
    await callback.answer()


@dp.callback_query(F.data == "adm_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await callback.message.answer("✍️ Введите текст объявления:")
    await callback.answer()


@dp.message(AdminStates.waiting_for_broadcast_text)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    broadcast_text = message.text.strip()
    await state.clear()
    data = load_data()
    success_count = 0
    for uid in data.get("users", {}).keys():
        try:
            await bot.send_message(chat_id=int(uid), text=f"📢 **ОБЪЯВЛЕНИЕ ОТ АДМИНА:**\n\n{broadcast_text}")
            success_count += 1
        except Exception:
            pass
    await message.answer(f"✅ Доставлено пользователям: {success_count}.")


@dp.callback_query(F.data == "adm_bonus")
async def admin_bonus_select(callback: types.CallbackQuery):
    await callback.message.answer("Кому выдать бонус?", reply_markup=get_users_inline_keyboard("bonus"))
    await callback.answer()


@dp.callback_query(F.data.startswith("bonus:"))
async def admin_bonus_get_pts(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target_uid=callback.data.split(":")[-1])
    await state.set_state(AdminStates.waiting_for_bonus_points)
    await callback.message.answer("✍ Сколько баллов добавить?:")
    await callback.answer()


@dp.message(AdminStates.waiting_for_bonus_points)
async def admin_bonus_apply(message: types.Message, state: FSMContext):
    try:
        pts = float(message.text.strip())
    except ValueError:
        return
    user_data = await state.get_data()
    target_uid = user_data.get("target_uid")
    await state.clear()
    data = load_data()
    if target_uid in data.get("users", {}):
        data["users"][target_uid]["points"] = min(100.0, data["users"][target_uid]["points"] + pts)
        data["history"].append({"user_id": target_uid, "user_name": "Администратор", "text": "🎁", "points": pts})
        save_data(data)
        await message.answer(f"✅ Добавлено +{pts} б.!")
        try:
            await bot.send_message(chat_id=int(target_uid), text=f"🎁 Начислен бонус: +{pts} баллов!")
        except Exception:
            pass


@dp.callback_query(F.data == "adm_penalty")
async def admin_penalty_select(callback: types.CallbackQuery):
    await callback.message.answer("Кого оштрафовать?", reply_markup=get_users_inline_keyboard("penalty"))
    await callback.answer()


@dp.callback_query(F.data.startswith("penalty:"))
async def admin_penalty_get_pts(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target_uid=callback.data.split(":")[-1])
    await state.set_state(AdminStates.waiting_for_penalty_points)


# --- НАЧИСЛЕНИЕ С ШТРАФОМ -5 ЗА ПРОВАЛ И ОГОНЬКАМИ ---
@dp.message(F.text.in_({"🔥 Сделал на отлично (+1)", "💪 Кое-что сделал (+0.5)", "💩 Забил на задачу (-5)"}))
async def add_points_simple(message: types.Message):
    data = load_data()
    user_id = str(message.from_user.id)
    init_user(data, user_id, message.from_user.full_name)

    if message.text == "🔥 Сделал на отлично (+1)":
        pts = 1.0
        data["users"][user_id]["done"] += 1
        msg = "🚀 +1 балл в рейтинг."
    elif message.text == "💪 Кое-что сделал (+0.5)":
        pts = 0.5
        data["users"][user_id]["done"] += 1
        msg = "🚜 +0.5 балла в рейтинг."
    else:
        pts = -5.0
        data["users"][user_id]["failed"] += 1
        msg = "🚨 Штраф -5 баллов!"

    data["users"][user_id]["points"] = min(100.0, data["users"][user_id]["points"] + pts)
    data["history"].append(
        {"user_id": user_id, "user_name": message.from_user.full_name, "text": message.text, "points": pts})
    save_data(data)
    status = get_status_text(data["users"][user_id]["points"])
    await message.answer(f"{msg}\n\nНовый РЕЙТИНГ: **{data['users'][user_id]['points']}**\nСтатус: {status}")


@dp.message(F.text == "🗑 Отменить моё последнее дело")
async def delete_last_simple(message: types.Message):
    data = load_data()
    user_id = str(message.from_user.id)
    user_action_index = None
    for i in range(len(data.get("history", [])) - 1, -1, -1):
        if data["history"][i]["user_id"] == user_id:
            user_action_index = i
            break
    if user_action_index is None:
        await message.answer("Удалять нечего!")
        return
    last_action = data["history"].pop(user_action_index)
    data["users"][user_id]["points"] = max(-100.0, data["users"][user_id]["points"] - last_action["points"])
    save_data(data)
    await message.answer("🗑 Действие отменено!")


# --- СИСТЕМНЫЙ СТАРТ И БУДИЛЬНИК ---
async def on_startup():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=0)
    scheduler.start()


async def main():
    asyncio.create_task(on_startup())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
