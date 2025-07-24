import asyncio
import os

import aiofiles
from aiogram import Router, F, Bot
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, BufferedInputFile
from aiogram.exceptions import (
    TelegramBadRequest, TelegramAPIError, TelegramForbiddenError,
    TelegramNotFound, TelegramRetryAfter
)
from config import ADMIN_ID, sql, bot
from src.keyboards.buttons import AdminPanel

msg_router = Router()

FAILED_USERS_FILE = "failed_users.txt"

# === HOLAT (FSM) === #
class MsgState(StatesGroup):
    forward_msg = State()
    send_msg = State()
    test_copy_msg = State()
    test_forward_msg = State()


# === QAYTISH TUGMASI === #
markup = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]]
)


# === ADMIN PANEL === #
@msg_router.message(F.text == "✍Xabarlar", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def panel_handler(message: Message) -> None:
    await message.answer("Xabarlar bo'limi!", reply_markup=await AdminPanel.admin_msg())


# === FORWARD XABAR BOSHLASH === #
@msg_router.message(F.text == "📨Forward xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_forward(message: Message, state: FSMContext):
    await message.answer("Forward yuboriladigan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.forward_msg)


# === FORWARD YUBORISH === #
@msg_router.message(MsgState.forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_forward_to_all(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    user_ids = [row[0] for row in rows]

    success, failed = await broadcast_forward(user_ids, message)

    await message.bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ Forward xabar yuborildi\n\n"
             f"📤 Yuborilgan: {success} ta\n"
             f"❌ Yuborilmagan: {failed} ta",
        reply_markup=await AdminPanel.admin_msg()
    )


# === ODDIY XABAR BOSHLASH === #
@msg_router.message(F.text == "📬Oddiy xabar yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def start_text_send(message: Message, state: FSMContext):
    await message.answer("Yuborilishi kerak bo'lgan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.send_msg)


# === ODDIY XABARNI YUBORISH === #
@msg_router.message(MsgState.send_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_text_to_all(message: Message, state: FSMContext):
    await state.clear()
    sql.execute("SELECT user_id FROM public.accounts")
    rows = sql.fetchall()
    user_ids = [row[0] for row in rows]

    success, failed = await broadcast_copy(user_ids, message)

    await message.answer(
        f"✅ Oddiy xabar yuborildi\n\n"
        f"📤 Yuborilgan: {success} ta\n"
        f"❌ Yuborilmagan: {failed} ta",
        reply_markup=await AdminPanel.admin_msg()
    )


# === ORQAGA QAYTISH === #
@msg_router.message(F.text == "🔙Orqaga qaytish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Orqaga qaytildi", reply_markup=await AdminPanel.admin_msg())


# === LOGGER: Xatolik foydalanuvchini faylga yozish === #
async def log_failed_user(user_id: int):
    async with aiofiles.open(FAILED_USERS_FILE, mode="a") as f:
        await f.write(f"{user_id}\n")


# === BROADCAST COPY YUBORISH (YAXSHILANGAN) === #
async def broadcast_copy(user_ids: list[int], message: Message) -> tuple[int, int]:
    success = 0
    failed = 0

    if os.path.exists(TEST_FAILED_COPY_FILE):
        os.remove(TEST_FAILED_COPY_FILE)

    status_msg = await message.answer("📤 Oddiy xabar yuborish boshlandi...")

    async def send_and_log(user_id):
        nonlocal success, failed
        for attempt in range(5):
            try:
                async with semaphore:
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )
                    success += 1
                    break
            except TelegramRetryAfter as e:
                print(f"[⏳ RetryAfter] {user_id=} -> {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                print(f"[🚫 Blocked] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=True)
                break
            except TelegramNotFound:
                print(f"[❌ Not Found] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=True)
                break
            except TelegramBadRequest as e:
                print(f"[⚠️ BadRequest] {user_id=}: {e}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=True)
                break
            except TelegramAPIError as e:
                print(f"[💥 API Error] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=True)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[❗ Unknown Error] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=True)
                await asyncio.sleep(2)
        await asyncio.sleep(0.3)

    tasks = [send_and_log(uid) for uid in user_ids]
    for i in range(0, len(tasks), 50):
        await asyncio.gather(*tasks[i:i + 50])
        try:
            await status_msg.edit_text(
                f"📬 Oddiy xabar yuborilmoqda...\n"
                f"✅ Yuborilgan: {success}\n"
                f"❌ Xato: {failed}\n"
                f"📦 Jami: {len(user_ids)} foydalanuvchi\n"
                f"📊 Progres: {min(i + 50, len(user_ids))}/{len(user_ids)}"
            )
        except Exception as e:
            print(f"⚠️ Holatni yangilashda xato: {e}")

    # Faylni yuborish
    if os.path.exists(TEST_FAILED_COPY_FILE):
        async with aiofiles.open(TEST_FAILED_COPY_FILE, "rb") as f:
            data = await f.read()
            file = BufferedInputFile(data, TEST_FAILED_COPY_FILE)
            await message.answer_document(file, caption="❌ Copy yuborishda xato bo‘lganlar")

    return success, failed


# === BROADCAST FORWARD YUBORISH (YAXSHILANGAN) === #
async def broadcast_forward(user_ids: list[int], message: Message) -> tuple[int, int]:
    success = 0
    failed = 0

    if os.path.exists(TEST_FAILED_FORWARD_FILE):
        os.remove(TEST_FAILED_FORWARD_FILE)

    status_msg = await message.answer("📨 Forward yuborish boshlandi...")

    async def send_and_log(user_id):
        nonlocal success, failed
        for attempt in range(5):
            try:
                async with semaphore:
                    await bot.forward_message(
                        chat_id=user_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )
                    success += 1
                    break
            except TelegramRetryAfter as e:
                print(f"[⏳ RetryAfter] {user_id=} -> {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                print(f"[🚫 Blocked] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=False)
                break
            except TelegramNotFound:
                print(f"[❌ Not Found] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=False)
                break
            except TelegramBadRequest as e:
                print(f"[⚠️ BadRequest] {user_id=}: {e}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=False)
                break
            except TelegramAPIError as e:
                print(f"[💥 API Error] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=False)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[❗ Unknown Error] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=False)
                await asyncio.sleep(2)
        await asyncio.sleep(0.6)

    tasks = [send_and_log(uid) for uid in user_ids]
    for i in range(0, len(tasks), 50):
        await asyncio.gather(*tasks[i:i + 50])
        try:
            await status_msg.edit_text(
                f"📨 Forward yuborilmoqda...\n"
                f"✅ Yuborilgan: {success}\n"
                f"❌ Xatolik: {failed}\n"
                f"📦 Jami: {len(user_ids)} foydalanuvchi\n"
                f"📊 Progres: {min(i + 50, len(user_ids))}/{len(user_ids)}"
            )
        except Exception as e:
            print(f"⚠️ Holatni yangilashda xato: {e}")

    # Faylni yuborish
    if os.path.exists(TEST_FAILED_FORWARD_FILE):
        async with aiofiles.open(TEST_FAILED_FORWARD_FILE, "rb") as f:
            data = await f.read()
            file = BufferedInputFile(data, TEST_FAILED_FORWARD_FILE)
            await message.answer_document(file, caption="❌ Forward yuborishda xato bo‘lganlar")

    return success, failed


TEST_FAILED_COPY_FILE = "test_failed_copy.txt"
TEST_FAILED_FORWARD_FILE = "test_failed_forward.txt"
semaphore = asyncio.Semaphore(20)

_logged_users_copy = set()
_logged_users_forward = set()



# === LOGGER: Xatolik foydalanuvchini faylga yozish (takror yozmaslik) === #
async def log_test_failed_user(user_id: int, is_copy=True):
    log_set = _logged_users_copy if is_copy else _logged_users_forward
    filename = TEST_FAILED_COPY_FILE if is_copy else TEST_FAILED_FORWARD_FILE

    if user_id in log_set:
        return
    log_set.add(user_id)
    async with aiofiles.open(filename, mode="a") as f:
        await f.write(f"{user_id}\n")

# === SINOV: COPY YUBORISH === #
@msg_router.message(F.text == "🧪Sinov: Copy yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_copy_broadcast(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov: Oddiy xabarni yuboring (copy), yuboriladi va darhol o‘chiriladi:")
    await state.set_state(MsgState.test_copy_msg)

@msg_router.message(MsgState.test_copy_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def handle_test_copy(message: Message, state: FSMContext):
    await state.clear()
    if os.path.exists(TEST_FAILED_COPY_FILE):
        os.remove(TEST_FAILED_COPY_FILE)

    sql.execute("SELECT user_id FROM public.accounts")
    user_ids = [row[0] for row in sql.fetchall()]

    success, failed = 0, 0
    status = await message.answer("📤 Sinov copy yuborish boshlandi...")

    async def send_and_delete(user_id):
        nonlocal success, failed
        for attempt in range(5):
            try:
                async with semaphore:
                    sent = await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )
                    await asyncio.sleep(0.2)
                    await bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                    success += 1
                    break
            except TelegramRetryAfter as e:
                print(f"[⏳ RetryAfter] {user_id=} -> {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                print(f"[🚫 Blocked] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=True)
                break
            except TelegramNotFound:
                print(f"[❌ Not Found] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=True)
                break
            except TelegramBadRequest as e:
                print(f"[⚠️ BadRequest] {user_id=}: {e}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=True)
                break
            except TelegramAPIError as e:
                print(f"[💥 API Error] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=True)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[❗ Unknown] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=True)
                await asyncio.sleep(2)
        await asyncio.sleep(0.2)

    tasks = [send_and_delete(uid) for uid in user_ids]
    for i in range(0, len(tasks), 50):
        await asyncio.gather(*tasks[i:i + 50])
        try:
            await status.edit_text(
                f"🧪 Copy sinovi\n"
                f"✅ Yuborildi: {success}\n"
                f"❌ Xato: {failed}\n"
                f"📊 Progres: {min(i + 50, len(user_ids))}/{len(user_ids)}"
            )
        except:
            pass

    await message.answer(f"✅ Sinov yakunlandi\n\n"
                         f"📤 Copy yuborilgan: {success}\n"
                         f"❌ Xatoliklar: {failed}\n"
                         f"📦 Jami: {len(user_ids)} foydalanuvchi")

    if os.path.exists(TEST_FAILED_COPY_FILE):
        async with aiofiles.open(TEST_FAILED_COPY_FILE, "rb") as f:
            data = await f.read()
            file = BufferedInputFile(data, TEST_FAILED_COPY_FILE)
            await message.answer_document(file, caption="❌ Copy yuborishda xato bo‘lganlar")


# === SINOV: FORWARD YUBORISH === #
@msg_router.message(F.text == "🧪Sinov: Forward yuborish", F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def test_forward_broadcast(message: Message, state: FSMContext):
    await message.answer("🧪 Sinov: Forward xabar yuboring, darhol o‘chiriladi:")
    await state.set_state(MsgState.test_forward_msg)

@msg_router.message(MsgState.test_forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def handle_test_forward(message: Message, state: FSMContext):
    await state.clear()
    if os.path.exists(TEST_FAILED_FORWARD_FILE):
        os.remove(TEST_FAILED_FORWARD_FILE)

    sql.execute("SELECT user_id FROM public.accounts")
    user_ids = [row[0] for row in sql.fetchall()]

    success, failed = 0, 0
    status = await message.answer("📨 Sinov forward yuborish boshlandi...")

    async def send_and_delete(user_id):
        nonlocal success, failed
        for attempt in range(5):
            try:
                async with semaphore:
                    sent = await bot.forward_message(
                        chat_id=user_id,
                        from_chat_id=message.chat.id,
                        message_id=message.message_id
                    )
                    await asyncio.sleep(0.2)
                    await bot.delete_message(chat_id=user_id, message_id=sent.message_id)
                    success += 1
                    break
            except TelegramRetryAfter as e:
                print(f"[⏳ RetryAfter] {user_id=} -> {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                print(f"[🚫 Blocked] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=False)
                break
            except TelegramNotFound:
                print(f"[❌ Not Found] {user_id=}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=False)
                break
            except TelegramBadRequest as e:
                print(f"[⚠️ BadRequest] {user_id=}: {e}")
                failed += 1
                await log_test_failed_user(user_id, is_copy=False)
                break
            except TelegramAPIError as e:
                print(f"[💥 API Error] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=False)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[❗ Unknown] {user_id=}: {e}")
                if attempt == 4:
                    failed += 1
                    await log_test_failed_user(user_id, is_copy=False)
                await asyncio.sleep(2)
        await asyncio.sleep(0.5)

    tasks = [send_and_delete(uid) for uid in user_ids]
    for i in range(0, len(tasks), 50):
        await asyncio.gather(*tasks[i:i + 50])
        try:
            await status.edit_text(
                f"🧪 Forward sinovi\n"
                f"✅ Yuborildi: {success}\n"
                f"❌ Xato: {failed}\n"
                f"📊 Progres: {min(i + 50, len(user_ids))}/{len(user_ids)}"
            )
        except:
            pass

    await message.answer(f"✅ Forward sinov tugadi\n\n"
                         f"📤 Forward yuborilgan: {success}\n"
                         f"❌ Xatoliklar: {failed}\n"
                         f"📦 Jami: {len(user_ids)} foydalanuvchi")

    if os.path.exists(TEST_FAILED_FORWARD_FILE):
        async with aiofiles.open(TEST_FAILED_FORWARD_FILE, "rb") as f:
            data = await f.read()
            file = BufferedInputFile(data, TEST_FAILED_FORWARD_FILE)
            await message.answer_document(file, caption="❌ Forward yuborishda xato bo‘lganlar")
