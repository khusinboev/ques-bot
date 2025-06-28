import os
import time
from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
)

from config import sql, bot, ADMIN_ID, cursor, conn, dp
from src.handlers.users.functions import format_results
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

user_router = Router()

WELCOME_TEXT_1 = (
    "<b>Assalomu alaykum, botimizga xush kelibsiz!</b>\n\n"
    "Ushbu bot orqali Oliy ta'lim muassasalariga kirish imtihonlariga <b>Bilimni baholash agentligi standardlariga</b> muvofiq <b>majburiy fanlar</b>dan tayyorgarlik ko'rishingiz mumkin. \n\n"
)

WELCOME_TEXT_2 = (
    "<b>@BMB_testbot orqali:</b>\n"
    "✅ Majburiy fanlardan bilim va ko'nikmalarni oshirish;\n"
    "✅ Kirish imtihonlariga tayyorgarlik;\n"
    "✅ Bilimni baholash imkoniyati mavjud.\n\n"
    "<b>♻️ Abituriyent do'stlaringizga ulashing!</b>"
)


async def handle_user_status(message_or_call, user_id, is_callback=False):
    sql.execute("SELECT member, ready, chance FROM public.referal WHERE user_id=%s", (user_id,))
    result = sql.fetchone()
    if not result:
        return

    member, ready, chance = result
    if member >= 3:
        cursor.execute("UPDATE referal SET ready=TRUE WHERE user_id = %s", (user_id,))
        conn.commit()

    cursor.execute("SELECT starter FROM referal WHERE user_id = %s", (user_id,))
    is_start = cursor.fetchone()[0]
    if is_start:
        cursor.execute("UPDATE referal SET starter = FALSE WHERE user_id = %s", (user_id,))
        conn.commit()

    if ready:
        await message_or_call.answer(WELCOME_TEXT_1, parse_mode="HTML")
        await message_or_call.answer(WELCOME_TEXT_2, parse_mode="HTML")

        await message_or_call.answer("<b>Kerakli bo'limni tanlang👇</b>", parse_mode="HTML",
                                     reply_markup=await UserPanels.ques_manu())
    elif chance:
        await message_or_call.answer(
            f"<b>Siz yana test ishlamoqchi bo'lsangiz quyidagi havola oraqali 3 ta do'stingizni taklif qiling:</b>\n"
            f"https://t.me/BMB_testbot?start={user_id}\n\n"
            f"Eslatma: 3 ta do'stingizni taklif qilgandan so'ng, sizga <b>cheksiz test ishlash</b> va <b>har bir fanda alohida</b> test ishlash imkoniyati taqdim etiladi.\n\n"
            f"Siz {member} ta odam taklif qildingiz, yana {3 - member} ta odam taklif qilishingiz kerak",
            parse_mode="HTML",
            reply_markup=await CheckData.share_link(user_id))
    else:
        await message_or_call.answer(WELCOME_TEXT_1, parse_mode="HTML")
        await message_or_call.answer(WELCOME_TEXT_2, parse_mode="HTML")
        await message_or_call.answer("<b>Kerakli bo'limni tanlang👇</b>", parse_mode="HTML",
                                     reply_markup=await UserPanels.chance_manu())

@user_router.message(CommandStart())
async def start_command(message: Message):
    await handle_user_status(message, message.from_user.id)

@user_router.callback_query(F.data == "check", F.message.chat.type == ChatType.PRIVATE)
async def check_channels(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        check_status, _ = await CheckData.check_member(bot, user_id)
        if check_status:
            await call.message.delete()
            await handle_user_status(call.message, user_id, is_callback=True)
        else:
            await call.answer(show_alert=True, text="Botimizdan foydalanish uchun barcha kanallarga a'zo bo'ling")
    except Exception as e:
        await bot.forward_message(chat_id=ADMIN_ID[0], from_chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.send_message(chat_id=ADMIN_ID[0], text=f"Error in check:\n{e}")

@dp.message(CommandStart(deep_link=True))
async def start_with_ref(message: Message, command: CommandObject):
    referal_id = command.args
    user_id = message.from_user.id

    if referal_id and str(user_id) != referal_id:
        cursor.execute("SELECT 1 FROM referal WHERE user_id = %s", (user_id,))
        if cursor.fetchone():
            cursor.execute("SELECT starter FROM referal WHERE user_id = %s", (user_id,))
            if cursor.fetchone()[0]:
                cursor.execute("UPDATE referal SET starter = FALSE WHERE user_id = %s", (user_id,))
                cursor.execute("UPDATE referal SET member = member + 1 WHERE user_id = %s", (referal_id,))
                conn.commit()

                cursor.execute("SELECT member FROM referal WHERE user_id = %s", (referal_id,))
                if cursor.fetchone()[0] >= 3:
                    cursor.execute("UPDATE referal SET ready=TRUE WHERE user_id = %s", (referal_id,))
                    conn.commit()
                    try:
                        await bot.send_message(chat_id=referal_id,
                                               text="Tabriklaymiz! Sizga cheksiz test ishlash imkoniyati taqdim etildi!",
                                               parse_mode="html",
                                               reply_markup=await UserPanels.ques_manu())
                    except:
                        pass

    await handle_user_status(message, user_id)

# Rasm fayllarni file_id ga yangilovchi funksiya
@user_router.message(F.text == "kepataqoy")
async def update_images(message: Message):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tables = ["history", "literature", "math"]
    for idx, table in enumerate(tables, 1):
        cursor.execute(f"SELECT id, photo FROM {table} WHERE file_id IS NULL")
        for row_id, photo_path in cursor.fetchall():
            full_path = os.path.join(current_dir, photo_path)
            if not os.path.exists(full_path):
                await message.answer(f"❌ Fayl topilmadi: {full_path}")
                continue
            with open(full_path, 'rb') as file:
                telegram_file = BufferedInputFile(file.read(), filename=os.path.basename(full_path))
            sent = await message.answer_photo(photo=telegram_file)
            file_id = sent.photo[-1].file_id
            cursor.execute(f"UPDATE {table} SET file_id = %s WHERE id = %s", (file_id, row_id))
            conn.commit()
            await message.answer(f"✅ {table} jadvalidan rasm yuborildi va yangilandi. {idx}")
            await sent.delete()
            time.sleep(0.1)
    await message.answer("✅ Barcha jadvalidagi rasm fayllari allaqachon file_id bilan yangilangan.")


@user_router.message(F.text == "📊Natijalarim")
async def natijalarim_handler(message: Message):
    user_id = message.from_user.id
    matn = format_results(user_id)
    await message.answer(matn, parse_mode="html")


# @user_router.message(F.text == "kepataqoy")
# async def start_cmd1(message: Message):
#     user_id = message.from_user.id
#     current_dir = os.path.dirname(os.path.abspath(__file__))
#
#     table_names = ["history", "literature", "math"]
#     nn = 0
#     for table in table_names:
#         nn+=1
#         cursor.execute(f"SELECT id, photo FROM {table} WHERE file_id IS NULL")
#         result = cursor.fetchall()
#
#         for row in result:
#
#             row_id, photo_path = row
#             full_path = os.path.join(current_dir, photo_path)
#
#             if not os.path.exists(full_path):
#                 await message.answer(f"❌ Fayl topilmadi: {full_path}")
#                 continue
#
#             with open(full_path, 'rb') as photo_file:
#                 photo_bytes = photo_file.read()
#
#             telegram_file = BufferedInputFile(photo_bytes, filename=os.path.basename(full_path))
#             sent_photo = await message.answer_photo(photo=telegram_file)
#
#             # file_id ni olish
#             file_id = sent_photo.photo[-1].file_id
#
#             # file_id ni jadvalga yangilash
#             cursor.execute(f"UPDATE {table} SET file_id = %s WHERE id = %s", (file_id, row_id))
#             conn.commit()
#             await message.answer(f"✅ {table} jadvalidan rasm yuborildi va yangilandi.{nn}")
#             await sent_photo.delete()
#             time.sleep(0.1)
#
#     else:
#         await message.answer("✅ Barcha jadvalidagi rasm fayllari allaqachon file_id bilan yangilangan.")