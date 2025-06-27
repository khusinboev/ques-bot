import os

from aiogram import Router, F
from aiogram.enums import ChatType
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQuery, \
    InlineQueryResultArticle, InputTextMessageContent, ChosenInlineResult

from config import sql, bot, ADMIN_ID, cursor, conn, dp
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

user_router = Router()

@user_router.message(CommandStart())
async def start_cmd1(message: Message):
    user_id = message.from_user.id
    is_start = cursor.execute("SELECT starter FROM referal WHERE user_id = %s", (user_id,)).fetchone()
    if is_start:
        cursor.execute(
            "UPDATE referal SET starter = TRUE WHERE user_id = %s", (user_id,)
        )
        conn.commit()

    sql.execute("SELECT ready, chance FROM public.referal WHERE user_id=%s", (user_id, ))
    result = sql.fetchone()
    if result:
        ready, chance = result
        if ready is True:
            await message.answer("Botimizga xush kelibsiz, kerakli bo'limni tanlab va davom eting!", parse_mode="html",
                                 reply_markup=await UserPanels.asos_manu())
        elif chance and ready is False:
            ref_link = f"https://t.me/BMB_testbot?start={user_id}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Referal havolangiz", url=ref_link)]
            ])
            await message.answer("Botimizga xush kelibsiz, Siz test sinovidagi boshlang'ich imkoniyatlaringizni foydalanib bo'lgansiz!\n\nSiz <b>5 ta do'stingizni botimizga taklif qiling</b> va <b>cheksiz</b> testlar ishlash imkoniyatini qo'lga kiriting!", parse_mode="html",
                                 reply_markup=kb)
        elif chance is False:
            await message.answer("Botimizga xush kelibsiz", reply_markup=await UserPanels.chance_manu())

@user_router.callback_query(F.data == "check", F.message.chat.type == ChatType.PRIVATE)
async def check(call: CallbackQuery):
    user_id = call.from_user.id
    try:
        check_status, channels = await CheckData.check_member(bot, user_id)
        if check_status:
            await call.message.delete()
            await bot.send_message(chat_id=user_id,
                                   text="Quyidagi menulardan birini tanlang!",
                                   parse_mode="html", reply_markup=await UserPanels.asos_manu())
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
        if cursor.fetchone():
            is_start = cursor.execute("SELECT starter FROM referal WHERE user_id = %s", (user_id,)).fetchone()
            if is_start:
                cursor.execute(
                    "UPDATE referal SET member = member + 1 WHERE user_id = %s", (referal_id,)
                )
                conn.commit()

                number = cursor.execute("SELECT member FROM referal WHERE user_id = %s", (referal_id,))
                if number>=5:
                    cursor.execute(
                        "UPDATE referal SET ready=TRUE WHERE user_id = %s", (referal_id,)
                    )
                    conn.commit()

    sql.execute("SELECT ready, chance FROM public.referal WHERE user_id=%s", (user_id,))
    result = sql.fetchone()
    if result:
        ready, chance = result
        if ready is True:
            await message.answer("Botimizga xush kelibsiz, kerakli bo'limni tanlab va davom eting!", parse_mode="html",
                                 reply_markup=await UserPanels.asos_manu())
        elif chance and ready is False:
            ref_link = f"https://t.me/BMB_testbot?start={user_id}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Referal havolangiz", url=ref_link)]
            ])
            await message.answer(
                "Botimizga xush kelibsiz, Siz test sinovidagi boshlang'ich imkoniyatlaringizni foydalanib bo'lgansiz!\n\nSiz <b>5 ta do'stingizni botimizga taklif qiling</b> va <b>cheksiz</b> testlar ishlash imkoniyatini qo'lga kiriting!",
                parse_mode="html",
                reply_markup=kb)
        elif chance is False:
            await message.answer("Botimizga xush kelibsiz", reply_markup=await UserPanels.chance_manu())