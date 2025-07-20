import asyncio
import csv
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

API_TOKEN = "7635754983:AAEoLA9QU0Aebg-M7a7NjRkZWUPKK5JrWaY"
ADMIN_CHAT_ID = 7569576915

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_data = {}

# Клавиатуры
def start_keyboard():
    return ReplyKeyboardBuilder().add(
        KeyboardButton(text="🛒 Сделать новый заказ"),
        KeyboardButton(text="💡 Предложить улучшение")
    ).as_markup(resize_keyboard=True)

def phone_keyboard():
    return ReplyKeyboardBuilder().add(
        KeyboardButton(text="📱 Отправить номер", request_contact=True)
    ).as_markup(resize_keyboard=True)

def confirm_keyboard():
    return ReplyKeyboardBuilder().add(
        KeyboardButton(text="✅ Подтвердить"),
        KeyboardButton(text="🔙 Назад"),
        KeyboardButton(text="🚫 Отменить заказ")
    ).as_markup(resize_keyboard=True)

def admin_inline_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить готовность", callback_data=f"ready_{user_id}")
    ]])

# Сохранение заказа
def save_order(user_id, name, phone, content, address, payment):
    with open("orders.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), user_id, name, phone, content, address, payment])

# Отправка админу
async def notify_admin(user_id, name, phone, content, address, payment, photo_id=None):
    text = (
        f"📦 *Новый заказ!*\n"
        f"👤 *Имя:* {name} (ID: `{user_id}`)\n"
        f"📞 *Телефон:* {phone}\n"
        f"📍 *Адрес:* {address}\n"
        f"🛒 *Заказ:* {content}\n"
        f"💳 *Оплата:* {payment}"
    )
    markup = admin_inline_keyboard(user_id)
    if photo_id:
        await bot.send_photo(ADMIN_CHAT_ID, photo=photo_id, caption=text, parse_mode="Markdown", reply_markup=markup)
    else:
        await bot.send_message(ADMIN_CHAT_ID, text, parse_mode="Markdown", reply_markup=markup)

# Старт
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id] = {"name": message.from_user.full_name}
    await message.answer(
        f"👋 Привет, {message.from_user.full_name}!\nЧтобы оформить заказ, нажми 🛒",
        reply_markup=start_keyboard()
    )

# Контакт
@dp.message(F.contact)
async def handle_contact(message: types.Message):
    user_id = message.from_user.id
    user_data.setdefault(user_id, {})["phone"] = message.contact.phone_number
    await message.answer("📥 Напишите список продуктов:")

# Фото
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    user_data.setdefault(user_id, {})["photo"] = message.photo[-1].file_id
    await message.answer("📷 Фото получено. Нажмите ✅ Подтвердить.")

# Подтверждение от админа
@dp.callback_query(F.data.startswith("ready_"))
async def handle_admin_ready(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_CHAT_ID:
        await callback.answer("⛔ Только админ может подтверждать.")
        return

    user_id = int(callback.data.split("_")[1])
    state = user_data.get(user_id)
    if not state:
        await callback.answer("❗ Заказ не найден.")
        return

    await bot.send_message(user_id, "🛒 Курьер собрал вашу корзину. Сейчас он укажет итоговую сумму.")
    await callback.message.answer("Введите итоговую сумму (например: 4700):")

    state["admin_step"] = "waiting_price_input"
    state["admin_chat_id"] = callback.from_user.id
    await callback.answer()

# Универсальный обработчик
@dp.message(F.text)
async def universal_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    state = user_data.setdefault(user_id, {})

    # Ввод суммы от админа
    if message.from_user.id == ADMIN_CHAT_ID and text.isdigit():
        for uid, s in user_data.items():
            if s.get("admin_step") == "waiting_price_input":
                s["total_price"] = text
                s["awaiting_payment"] = True
                s["admin_step"] = None

                await bot.send_message(
                    uid,
                    f"💰 Общая сумма заказа: {text}₸ (включая доставку).\n\n"
                    f"💳 Оплатите переводом через *Kaspi* на номер *+77762266381* "
                    f"и нажмите кнопку \"💸 Оплата произведена\".",
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardBuilder().add(
                        KeyboardButton(text="💸 Оплата произведена")
                    ).as_markup(resize_keyboard=True)
                )
                await message.answer("✅ Сумма отправлена клиенту.")
                return

    # Обратная связь
    if state.get("feedback"):
        await bot.send_message(ADMIN_CHAT_ID, f"💡 Предложение от {state['name']}:\n{text}")
        state.pop("feedback")
        await message.answer("✅ Спасибо! Ваше предложение получено.", reply_markup=start_keyboard())
        return

    # Новый заказ после завершения
    if state.get("finished"):
        if text == "🛒 Сделать новый заказ":
            user_data[user_id] = {"name": message.from_user.full_name}
            await message.answer("📱 Отправьте номер телефона:", reply_markup=phone_keyboard())
        else:
            await message.answer("ℹ️ Заказ уже оформлен. Нажмите 🛒, чтобы начать новый.")
        return

    # Предложение
    if text == "💡 Предложить улучшение":
        state["feedback"] = True
        await message.answer("✍ Напишите ваше предложение:")
        return

    # Отмена
    if text == "🚫 Отменить заказ":
        user_data.pop(user_id, None)
        await message.answer("🚫 Заказ отменён.", reply_markup=start_keyboard())
        return

    # Назад
    if text == "🔙 Назад":
        for key in ["photo", "address", "products"]:
            if key in state:
                state.pop(key)
                await message.answer(f"🔁 Назад. Введите {key}.")
                return
        await start_cmd(message)
        return

    # Новый заказ
    if text == "🛒 Сделать новый заказ":
        user_data[user_id] = {"name": message.from_user.full_name}
        await message.answer("📱 Отправьте номер телефона:", reply_markup=phone_keyboard())
        return

    # Шаги
    if "phone" not in state:
        await message.answer("📱 Сначала отправьте номер телефона.", reply_markup=phone_keyboard())
        return

    if "products" not in state:
        state["products"] = text
        await message.answer("📍 Укажите адрес доставки:")
        return

    if "address" not in state:
        state["address"] = text
        state["payment"] = "не указан"
        await message.answer("📸 Прикрепите фото (если нужно) или нажмите ✅ Подтвердить.", reply_markup=confirm_keyboard())
        return

    if text == "✅ Подтвердить":
        await notify_admin(
            user_id, state["name"], state["phone"],
            state["products"], state["address"],
            state["payment"], state.get("photo")
        )
        save_order(user_id, state["name"], state["phone"], state["products"], state["address"], state["payment"])
        state["finished"] = False
        await message.answer("✅ Заказ оформлен. Ожидайте подтверждения от курьера.", reply_markup=ReplyKeyboardRemove())
        return

    if text == "💸 Оплата произведена":
        if not state.get("awaiting_payment"):
            await message.answer("⛔ Нет ожидающей оплаты.")
            return

        await bot.send_message(
            ADMIN_CHAT_ID,
            f"✅ Оплата подтверждена клиентом {state['name']} (ID: {user_id})"
        )

        state["awaiting_payment"] = False
        state["finished"] = True

        await message.answer(
            "✅ Спасибо! Курьер уже выехал к вам.",
            reply_markup=ReplyKeyboardRemove()
        )

        new_order_kb = ReplyKeyboardBuilder().add(
            KeyboardButton(text="🛒 Сделать новый заказ")
        ).as_markup(resize_keyboard=True)

        await message.answer("🛍 Хотите оформить новый заказ?", reply_markup=new_order_kb)
        return

# Запуск
async def main():
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
