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

from config import sql, db, bot
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
async def start_all_subjects(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if check_status:
        user_id = message.from_user.id
        sql.execute("SELECT 1 FROM referal WHERE user_id = %s;", (user_id,))
        if sql.fetchone():
            sql.execute("UPDATE referal SET chance = TRUE WHERE user_id = %s;", (user_id,))
            db.commit()
        subjects = [("literature", "Ona tili"), ("math", "Matematika"), ("history", "Tarix")]
        selected_all = []
        stats = {}

        for table_name, subject_name in subjects:
            sql.execute(f"SELECT DISTINCT varyant FROM {table_name} WHERE status='True'")
            variants = sql.fetchall()
            if not variants:
                await message.answer(f"{subject_name} fanida mavjud variant topilmadi.")
                return
            selected_v = random.choice([v[0] for v in variants])
            sql.execute(f"SELECT file_id, answer FROM {table_name} WHERE varyant=%s AND status='True'", (selected_v,))
            questions = sql.fetchall()
            if len(questions) < 10:
                await message.answer(f"{subject_name} fanida {selected_v}-variantdan yetarli test yo'q.")
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
        await message.answer("📚 3 ta fandan umumiy test boshlandi", reply_markup=ReplyKeyboardRemove())
        await show_question(message, selected_all[0], 0, 0.0, state)
    else:
        await message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                             reply_markup=await CheckData.channels_btn(channels))


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
        f"⏱ O‘tgan vaqt: {time_elapsed // 60} daqiqa {time_elapsed % 60} soniya | Qolgan: {time_left // 60} daq. {time_left % 60} son.")

    if isinstance(message_or_callback, Message):
        await message_or_callback.answer_photo(photo=photo, caption=caption, reply_markup=btn, parse_mode="HTML")
    else:
        try:
            await message_or_callback.message.edit_media(
                InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"))
            await message_or_callback.message.edit_reply_markup(reply_markup=btn)
        except:
            pass
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
        result += f"\n\nUmumiy: {int((score + 0.01) // 1.1)} ta to‘g‘ri | {round(score, 1)} ball"
        result += f"\n⏳ {elapsed // 60} daqiqa {elapsed % 60} soniyada yakunlandi"

        await callback.message.answer(result, reply_markup=await UserPanels.ques_manu())
        await callback.message.delete()
        await state.clear()


@check_router.callback_query(F.data == "stop-checkup")
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    user_id = callback.message.from_user.id
    sql.execute("SELECT ready, chance FROM public.referal WHERE user_id=%s", (user_id, ))
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
                f"<b>Siz yana test ishlamoqchi bo'lsangiz quyidagi havola oraqali 3 ta do'stingizni taklif qiling:</b> \n<code>https://t.me/BMB_testbot?start={user_id}</code>\n\nEslatma: 3 ta do'stingizni taklif qilgandan so'ng, sizga <b>cheksiz test ishlash</b> hamda <b>har bir fanda alohida</b> test ishlash imkoniyati taqdim etiladi.\nSiz {number} ta odam taklif qildingiz, yana {3 - number}ta odam taklif qilishingiz kerak",
                parse_mode="html",
                reply_markup=await CheckData.share_link(user_id))
        elif chance is False:
            await callback.message.answer("Botimizga xush kelibsiz", reply_markup=await UserPanels.chance_manu())
        print("bera")
    except:
        await callback.message.answer("/start")
