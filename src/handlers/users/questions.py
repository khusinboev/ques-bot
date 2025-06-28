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

from config import cursor, sql, bot
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData

ques_router = Router()


class FormQues(StatesGroup):
    ques_list = State()
    current_index = State()
    score = State()
    end_time = State()
    subject_stats = State()  # dict: {subject: {'correct': int, 'score': float}}
    start_time = State()

# Fan boshlash tugmalari
def confirm_test_btn(subject_code: str, subject_name: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Boshlash", callback_data=f"confirm_start:{subject_code}:{subject_name}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back-to-menu")]
    ])

@ques_router.message(F.text == "📝 Matematika️")
async def choose_math(message: Message):
    await message.answer("📝 Matematika fanidan testni boshlashni xohlaysizmi?",
                         reply_markup=confirm_test_btn("math", "Matematika"))

@ques_router.message(F.text == "📚 Ona tili")
async def choose_literature(message: Message):
    await message.answer("📚 Ona tili fanidan testni boshlashni xohlaysizmi?",
                         reply_markup=confirm_test_btn("literature", "Ona tili"))

@ques_router.message(F.text == "📚 Tarix")
async def choose_history(message: Message):
    await message.answer("📚 O‘zbekiston tarixi fanidan testni boshlashni xohlaysizmi?",
                         reply_markup=confirm_test_btn("history", "O‘zbekiston tarixi"))

@ques_router.message(F.text == "🧮 Hamasidan")
async def choose_all_subjects(message: Message):
    await message.answer("🧮 3 ta fandan umumiy testni boshlashni xohlaysizmi?",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="✅ Boshlash", callback_data="confirm_start:all:all")],
                             [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back-to-menu")]
                         ]))


@ques_router.callback_query(F.data.startswith("confirm_start:"))
async def confirm_start_test(callback: CallbackQuery, state: FSMContext):
    _, subject_code, subject_name = callback.data.split(":")

    check_status, channels = await CheckData.check_member(bot, callback.from_user.id)
    if not check_status:
        await callback.message.delete()
        await callback.message.edit_text(
            "❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
            reply_markup=await CheckData.channels_btn(channels)
        )
        return

    if subject_code == "all":
        await start_all_subjects(callback.message, state)
    else:
        await start_subject(callback.message, state, subject_code, subject_name, duration=20 * 60)


@ques_router.callback_query(F.data == "back-to-menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "📚 Majburiy fanlardan test ishlash bo‘limiga qaytdingiz, kerakli fanni tanlang.",
        reply_markup=await UserPanels.ques_manu()
    )

async def start_all_subjects(message: Message, state: FSMContext):
    check_status, channels = await CheckData.check_member(bot, message.from_user.id)
    if check_status:
        try:
            await message.delete()
        except:
            pass

        subjects = [("literature", "Ona tili"), ("math", "Matematika"), ("history", "O‘zbekiston tarixi")]
        selected_all = []
        stats = {}

        for table_name, subject_name in subjects:
            cursor.execute(f"SELECT DISTINCT varyant FROM {table_name} WHERE status='True'")
            variants = cursor.fetchall()
            if not variants:
                await message.answer(f"{subject_name} fanida mavjud variant topilmadi.")
                return
            selected_v = random.choice([v[0] for v in variants])
            cursor.execute(f"SELECT file_id, answer FROM {table_name} WHERE varyant=%s AND status='True'", (selected_v,))
            questions = cursor.fetchall()
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


async def start_subject(message: Message, state: FSMContext, table_name: str, subject_name: str, duration: int):
    try:
        await message.delete()
    except:
        pass

    cursor.execute(f"SELECT DISTINCT varyant FROM {table_name} WHERE status='True'")
    variants = cursor.fetchall()
    if not variants:
        await message.answer("Fan uchun variantlar topilmadi.")
        return
    selected_variant = random.choice([v[0] for v in variants])
    cursor.execute(f"SELECT file_id, answer FROM {table_name} WHERE varyant=%s AND status='True'", (selected_variant,))
    questions = cursor.fetchall()
    if len(questions) < 10:
        await message.answer("Yetarlicha test mavjud emas.")
        return

    selected = [(q[0], q[1], subject_name) for q in random.sample(questions, 10)]
    end_time = asyncio.get_event_loop().time() + duration
    start_time = asyncio.get_event_loop().time()

    await state.set_data({
        "ques_list": selected,
        "current_index": 0,
        "score": 0.0,
        "total_questions": len(selected),
        "end_time": end_time,
        "subject_stats": {subject_name: {'correct': 0, 'score': 0.0}},
        "start_time": start_time
    })

    await message.answer(f"Test boshlandi ({selected_variant}-variant)", reply_markup=ReplyKeyboardRemove())
    await show_question(message, selected[0], 0, 0.0, state)


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
                    callback_data=f"answer:{option}:{suffix}:{index}:{score}:{subject_name}"
                )
            )
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⛔ To‘xtatish", callback_data="stop-quest")])
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


@ques_router.callback_query(F.data.startswith("answer:"))
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


@ques_router.callback_query(F.data == "stop-quest")
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Majburiy bloklardan test ishlash bo'limiga xush kelibsiz, kerakli fanni tanlang va davom eting!",
        parse_mode="html",
        reply_markup=await UserPanels.ques_manu()
    )
    await callback.message.delete()
