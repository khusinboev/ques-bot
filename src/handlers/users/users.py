import os

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult, BufferedInputFile

from config import sql, bot, ADMIN_ID, cursor, conn, dp
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

user_router = Router()

@user_router.message(CommandStart())
async def start_cmd1(message: Message):
    user_id = message.from_user.id
    sql.execute("SELECT member FROM public.referal WHERE user_id=%s", (user_id,))
    numb = sql.fetchone()[0]
    if numb >= 3:
        cursor.execute("UPDATE referal SET ready=TRUE WHERE user_id = %s", (user_id,))
        conn.commit()
    cursor.execute("SELECT starter FROM referal WHERE user_id = %s", (user_id,))
    is_start = cursor.fetchone()[0]
    if is_start:
        print(is_start)
        cursor.execute(
            "UPDATE referal SET starter = FALSE WHERE user_id = %s", (user_id,)
        )
        conn.commit()
    sql.execute("SELECT ready, chance FROM public.referal WHERE user_id=%s", (user_id, ))
    result = sql.fetchone()
    if result:
        ready, chance = result
        if ready is True:
            await message.answer(
                "Tabriklaymiz! Sizga cheksiz test ishlash imkoniyati taqdim etildi!",
                parse_mode="html",
                reply_markup=await UserPanels.ques_manu()
            )
        elif chance and ready is False:
            sql.execute("SELECT member FROM public.referal WHERE user_id=%s", (user_id,))
            number = sql.fetchone()
            await message.answer(
                f"<b>Siz yana test ishlamoqchi bo'lsangiz quyidagi havola oraqali 3 ta do'stingizni taklif qiling:</b> \n<code>https://t.me/BMB_testbot?start={user_id}</code>\n\nEslatma: 3 ta do'stingizni taklif qilgandan so'ng, sizga <b>cheksiz test ishlash</b> hamda <b>har bir fanda alohida</b> test ishlash imkoniyati taqdim etiladi.\nSiz {number[0]} ta odam taklif qildingiz, yana {3 - number[0]}ta odam taklif qilishingiz kerak",
                parse_mode="html",
                reply_markup=await CheckData.share_link(user_id))
        elif chance is False:
            await message.answer("Botimizga xush kelibsiz", reply_markup=await UserPanels.chance_manu())

@user_router.callback_query(F.data == "check", F.message.chat.type == ChatType.PRIVATE)
async def check(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        check_status, channels = await CheckData.check_member(bot, user_id)
        if check_status:
            await call.message.delete()
            user_id = call.message.from_user.id
            sql.execute("SELECT member FROM public.referal WHERE user_id=%s", (user_id,))
            numb = sql.fetchone()[0]
            if numb >= 3:
                cursor.execute("UPDATE referal SET ready=TRUE WHERE user_id = %s", (user_id,))
                conn.commit()
            cursor.execute("SELECT starter FROM referal WHERE user_id = %s", (user_id,))
            is_start = cursor.fetchone()[0]
            if is_start:
                print(is_start)
                cursor.execute(
                    "UPDATE referal SET starter = FALSE WHERE user_id = %s", (user_id,)
                )
                conn.commit()
            sql.execute("SELECT ready, chance FROM public.referal WHERE user_id=%s", (user_id,))
            result = sql.fetchone()
            if result:
                ready, chance = result
                if ready is True:
                    await call.message.answer(
                        "Tabriklaymiz! Sizga cheksiz test ishlash imkoniyati taqdim etildi!",
                        parse_mode="html",
                        reply_markup=await UserPanels.ques_manu()
                    )
                elif chance and ready is False:
                    sql.execute("SELECT member FROM public.referal WHERE user_id=%s", (user_id,))
                    number = sql.fetchone()
                    await call.message.answer(
                        f"<b>Siz yana test ishlamoqchi bo'lsangiz quyidagi havola oraqali 3 ta do'stingizni taklif qiling:</b> \n<code>https://t.me/BMB_testbot?start={user_id}</code>\n\nEslatma: 3 ta do'stingizni taklif qilgandan so'ng, sizga <b>cheksiz test ishlash</b> hamda <b>har bir fanda alohida</b> test ishlash imkoniyati taqdim etiladi.\nSiz {number[0]} ta odam taklif qildingiz, yana {3 - number[0]}ta odam taklif qilishingiz kerak",
                        parse_mode="html",
                        reply_markup=await CheckData.share_link(user_id))
                elif chance is False:
                    await call.message.answer("Botimizga xush kelibsiz", reply_markup=await UserPanels.chance_manu())
            try:
                await call.answer()
            except:
                pass
        else:
            try:
                await call.answer(show_alert=True, text="Botimizdan foydalanish uchun barcha kanallarga a'zo bo'ling")
            except:
                try:
                    await call.answer()
                except:
                    pass
    except Exception as e:
        await bot.forward_message(chat_id=ADMIN_ID[0], from_chat_id=call.message.chat.id, message_id=call.message.message_id)
        await bot.send_message(chat_id=ADMIN_ID[0], text=f"Error in check:\n{e}")


@dp.message(CommandStart(deep_link=True))
async def start_with_ref(message: Message, command: CommandObject):
    referal_id = command.args  # bu yerda referal user_id bo'ladi
    user_id = message.from_user.id

    if referal_id and str(user_id) != referal_id:
        # Baza orqali tekshirib, yozamiz
        cursor.execute("SELECT 1 FROM referal WHERE user_id = %s", (user_id,))
        checks = cursor.fetchone()[0]
        print(checks)
        if checks:
            cursor.execute("SELECT starter FROM referal WHERE user_id = %s", (user_id,))
            is_start = cursor.fetchone()[0]
            if is_start:
                print(is_start)
                cursor.execute(
                    "UPDATE referal SET starter=%s WHERE user_id = %s", (False, user_id,)
                )
                conn.commit()
                cursor.execute(
                    "UPDATE referal SET member = member + 1 WHERE user_id = %s", (referal_id,)
                )
                conn.commit()

                cursor.execute("SELECT member FROM referal WHERE user_id = %s", (referal_id,))
                number = cursor.fetchone()[0]
                if number>=3:
                    cursor.execute(
                        "UPDATE referal SET ready=TRUE WHERE user_id = %s", (referal_id,)
                    )
                    conn.commit()
                    try:
                        await bot.send_message(chat_id=referal_id,
                                               text="Tabriklaymiz! Sizga cheksiz test ishlash imkoniyati taqdim etildi!",
                                               parse_mode="html",
                                               reply_markup=await UserPanels.ques_manu())
                    except: pass

    sql.execute("SELECT ready, chance FROM public.referal WHERE user_id=%s", (user_id,))
    result = sql.fetchone()
    if result:
        ready, chance = result
        if ready is True:
            await message.answer(
                "Tabriklaymiz! Sizga cheksiz test ishlash imkoniyati taqdim etildi!",
                parse_mode="html",
                reply_markup=await UserPanels.ques_manu()
            )
        elif chance and ready is False:
            sql.execute("SELECT member FROM public.referal WHERE user_id=%s", (user_id,))
            number = sql.fetchone()
            await message.answer(
                f"<b>Siz yana test ishlamoqchi bo'lsangiz quyidagi havola oraqali 3 ta do'stingizni taklif qiling:</b> \n<code>https://t.me/BMB_testbot?start={user_id}</code>\n\nEslatma: 3 ta do'stingizni taklif qilgandan so'ng, sizga <b>cheksiz test ishlash</b> hamda <b>har bir fanda alohida</b> test ishlash imkoniyati taqdim etiladi.\nSiz {number[0]} ta odam taklif qildingiz, yana {3 - number[0]}ta odam taklif qilishingiz kerak",
                parse_mode="html",
                reply_markup=await CheckData.share_link(user_id))
        elif chance is False:
            await message.answer("Botimizga xush kelibsiz", reply_markup=await UserPanels.chance_manu())


@user_router.message(F.text == "kepataqoy")
async def start_cmd1(message: Message):
    user_id = message.from_user.id
    current_dir = os.path.dirname(os.path.abspath(__file__))

    table_names = ["history", "literature", "math"]
    nn = 0
    for table in table_names:
        nn+=1
        cursor.execute(f"SELECT id, photo FROM {table} WHERE file_id IS NULL")
        result = cursor.fetchall()

        for row in result:

            row_id, photo_path = row
            full_path = os.path.join(current_dir, photo_path)

            if not os.path.exists(full_path):
                await message.answer(f"❌ Fayl topilmadi: {full_path}")
                continue

            with open(full_path, 'rb') as photo_file:
                photo_bytes = photo_file.read()

            telegram_file = BufferedInputFile(photo_bytes, filename=os.path.basename(full_path))
            sent_photo = await message.answer_photo(photo=telegram_file)

            # file_id ni olish
            file_id = sent_photo.photo[-1].file_id

            # file_id ni jadvalga yangilash
            cursor.execute(f"UPDATE {table} SET file_id = %s WHERE id = %s", (file_id, row_id))
            conn.commit()
            await message.answer(f"✅ {table} jadvalidan rasm yuborildi va yangilandi.{nn}")
            await sent_photo.delete()

    else:
        await message.answer("✅ Barcha jadvalidagi rasm fayllari allaqachon file_id bilan yangilangan.")