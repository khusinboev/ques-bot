import os
import random
import asyncio
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, BufferedInputFile, InputMediaPhoto, ReplyKeyboardRemove
)

from config import sql, db, bot, cursor, conn
from src.handlers.users.questions import insert_result
from src.handlers.users.users import WELCOME_TEXT
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

check_router = Router()


class FormQues(StatesGroup):
    ques_list = State()
    current_index = State()
    score = State()
    end_time = State()
    subject_stats = State()
    start_time = State()


@check_router.message(F.text == "📚 Majburiy blokdan test ishlash")
async def show_start_buttons(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Boshlash", callback_data="start-mandatory-test")]
    ])
    await message.answer("📝 Majburiy fanlardan test ishlashni boshlash uchun quyidagi tugmalardan birini tanlang:", reply_markup=keyboard)

@check_router.callback_query(F.data == "start-mandatory-test")
async def start_test_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    check_status, channels = await CheckData.check_member(bot, user_id)
    if not check_status:
        await callback.message.delete()
        await callback.message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                                      reply_markup=await CheckData.channels_btn(channels))
        return

    sql.execute("SELECT 1 FROM referal WHERE user_id = %s;", (user_id,))
    if sql.fetchone():
        sql.execute("UPDATE referal SET chance = TRUE WHERE user_id = %s;", (user_id,))
        db.commit()

    subjects = [("literature", "Ona tili"), ("math", "Matematika"), ("history", "O‘zbekiston tarixi")]
    selected_all = []
    stats = {}

    for table_name, subject_name in subjects:
        sql.execute(f"SELECT DISTINCT varyant FROM {table_name} WHERE status='True'")
        variants = sql.fetchall()
        if not variants:
            await callback.message.answer(f"{subject_name} fanida mavjud variant topilmadi.")
            return
        selected_v = random.choice([v[0] for v in variants])
        sql.execute(f"SELECT file_id, answer FROM {table_name} WHERE varyant=%s AND status='True'", (selected_v,))
        questions = sql.fetchall()
        if len(questions) < 10:
            await callback.message.answer(f"{subject_name} fanida {selected_v}-variantdan yetarli test yo'q.")
            return
        sample = random.sample(questions, 10)
        selected_all.extend([(q[0], q[1], subject_name) for q in sample])
        stats[subject_name] = {'correct': 0, 'score': 0.0}

    end_time = asyncio.get_event_loop().time() + 60 * 60
    start_time = asyncio.get_event_loop().time()

    await state.set_data({
        "ques_list": selected_all,
        "current_index": 0,
        "score": 0.0,
        "total_questions": len(selected_all),
        "end_time": end_time,
        "subject_stats": stats,
        "start_time": start_time
    })
    await callback.message.delete()
    await callback.message.answer("📚 3 ta fandan umumiy test boshlandi", reply_markup=ReplyKeyboardRemove())
    print(selected_all[0])
    await show_question(callback, selected_all[0], 0, 0.0, state)



async def show_question(message_or_callback, question, index, score, state: FSMContext):
    data = await state.get_data()
    total_questions = data.get("total_questions", 10)
    end_time = data.get("end_time")
    now = asyncio.get_event_loop().time()

    if now > end_time:
        await force_finish(message_or_callback, state)
        return

    time_left = int(end_time - now)
    time_elapsed = int(now - data.get("start_time", now))

    photo, correct_answer, subject_name = question

    variants = ["A", "B", "C", "D"]
    keyboard = []
    for i in range(0, 4, 2):
        row = []
        for option in variants[i:i + 2]:
            suffix = "+" if option.lower() == str(correct_answer).lower() else "-"
            row.append(
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"1answer:{option}:{suffix}:{index}:{score}:{subject_name}"
                )
            )
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⛔ To‘xtatish", callback_data="stop-checkup")])
    btn = InlineKeyboardMarkup(inline_keyboard=keyboard)

    caption = (
        f"📖 FAN: <b>{subject_name}</b>\n"
        f"🧮 <b>Savol: {index + 1} / {total_questions}</b>\n"
        f"⏱ O‘tgan vaqt: {time_elapsed // 60} daqiqa {time_elapsed % 60} soniya | "
        f"Qolgan: {time_left // 60} daq. {time_left % 60} son."
    )

    if isinstance(message_or_callback, Message):
        # Foydalanuvchiga yangi savolni yuborish
        await message_or_callback.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=btn,
            parse_mode="HTML"
        )
    elif isinstance(message_or_callback, CallbackQuery):
        try:
            media = InputMediaPhoto(
                media=photo,
                caption=caption,
                parse_mode="HTML"
            )
            await message_or_callback.message.edit_media(
                media=media,
                reply_markup=btn
            )
        except Exception as e:
            print(f"[edit error] {e}")
        await message_or_callback.answer()



async def force_finish(message_or_callback, state: FSMContext):
    data = await state.get_data()
    score = data.get("score", 0.0)
    stats = data.get("subject_stats", {})
    questions = data.get("ques_list", [])
    elapsed = int(asyncio.get_event_loop().time() - data.get("start_time", 0))

    result = "⏱ Vaqt tugadi!\n"
    for subject, info in stats.items():
        result += f"\n📘 {subject}: {info['correct']} ta to‘g‘ri | {round(info['score'], 1)} ball"
    result += f"\n\nUmumiy: {int((score + 0.01) // 1.1)} ta to‘g‘ri | {round(score, 1)} ball"
    result += f"\n⏳ {elapsed // 60} daqiqa {elapsed % 60} soniyada yakunlandi"

    await message_or_callback.answer(result, reply_markup=await UserPanels.ques_manu())
    await state.clear()


@check_router.callback_query(F.data.startswith("1answer:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split(":")
    is_correct = data[2]
    index = int(data[3])
    score = float(data[4])
    subject = data[5]

    state_data = await state.get_data()
    end_time = state_data.get("end_time")
    if asyncio.get_event_loop().time() > end_time:
        await force_finish(callback, state)
        return

    if is_correct == "+":
        score += 1.1
        state_data["subject_stats"][subject]["correct"] += 1
        state_data["subject_stats"][subject]["score"] += 1.1

    questions = state_data.get("ques_list")
    next_index = index + 1

    if next_index < len(questions):
        await state.update_data(current_index=next_index, score=score, subject_stats=state_data["subject_stats"])
        await show_question(callback, questions[next_index], next_index, score, state)
    else:
        elapsed = int(asyncio.get_event_loop().time() - state_data.get("start_time", 0))
        result = "✅ Test yakunlandi!\n"
        for subject, info in state_data["subject_stats"].items():
            result += f"\n📘 {subject}: {info['correct']} ta to‘g‘ri | {round(info['score'], 1)} ball"
            insert_result(user_id=callback.from_user.id,
                          subject={"Ona tili": "literature", "Matematika": "math", "O‘zbekiston tarixi": "history"}[
                              subject], number=info['correct'])
        result += f"\n\nUmumiy: {int((score + 0.01) // 1.1)} ta to‘g‘ri | {round(score, 1)} ball"
        result += f"\n⏳ {elapsed // 60} daqiqa {elapsed % 60} soniyada yakunlandi"

        await callback.message.answer(result, reply_markup=await UserPanels.ques_manu())
        try:
            await callback.message.delete()
        except:
            pass
        await state.clear()
        user_id = callback.message.from_user.id
        sql.execute("SELECT ready, chance FROM public.referal WHERE user_id=%s", (user_id,))
        result = sql.fetchone()
        try:
            ready, chance = result
            if ready is True:
                await callback.message.answer(
                    "Tabriklaymiz! Sizga cheksiz test ishlash imkoniyati taqdim etildi!",
                    parse_mode="html",
                    reply_markup=await UserPanels.ques_manu()
                )
            elif chance and ready is False:
                sql.execute("SELECT member FROM public.referal WHERE user_id=%s", (user_id,))
                number = sql.fetchone()
                await callback.message.answer("Botimizga xush kelibsiz", reply_markup=ReplyKeyboardRemove())
                await callback.message.answer(
                    f"<b>Siz yana test ishlamoqchi bo'lsangiz quyidagi havola oraqali 3 ta do'stingizni taklif qiling:</b> \nhttps://t.me/BMB_testbot?start={user_id}\n\nEslatma: 3 ta do'stingizni taklif qilgandan so'ng, sizga <b>cheksiz test ishlash</b> hamda <b>har bir fanda alohida</b> test ishlash imkoniyati taqdim etiladi.\n\nSiz {number[0]} ta odam taklif qildingiz, yana {3 - number[0]}ta odam taklif qilishingiz kerak",
                    parse_mode="html",
                    reply_markup=await CheckData.share_link(user_id))
            elif chance is False:
                await callback.message.answer("Botimizga xush kelibsiz", reply_markup=await UserPanels.chance_manu())
            print("bera")
        except Exception as e:
            print(e)
            await callback.message.answer("/start")

async def handle_user_status2(message_or_call, user_id, is_callback=False):
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
        await message_or_call.answer(WELCOME_TEXT, parse_mode="HTML")
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
        await message_or_call.answer(WELCOME_TEXT, parse_mode="HTML")
        await message_or_call.answer("<b>Kerakli bo'limni tanlang👇</b>", parse_mode="HTML",
                                     reply_markup=await UserPanels.chance_manu())

@check_router.callback_query(F.data == "stop-checkup")
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await handle_user_status2(callback.message, callback.from_user.id)
