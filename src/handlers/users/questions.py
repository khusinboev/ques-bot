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

from config import cursor, sql, bot, conn
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
    user_id = callback.from_user.id

    # 1. Kanalga a'zolikni tekshirish
    check_status, channels = await CheckData.check_member(bot, user_id)
    if not check_status:
        await callback.message.delete()
        await callback.message.answer(
            "❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
            reply_markup=await CheckData.channels_btn(channels)
        )
        return

    # 2. referal holatini tekshirish (yo‘q bo‘lsa yaratamiz)
    sql.execute("SELECT ready, chance, starter, member FROM referal WHERE user_id = %s", (user_id,))
    row = sql.fetchone()

    if not row:
        # Birinchi kirgan foydalanuvchi — 1 martalik testga ruxsat beriladi
        sql.execute("""
            INSERT INTO referal (user_id, ready, chance, starter, member)
            VALUES (%s, FALSE, TRUE, TRUE, 0)
        """, (user_id,))
        db.commit()
        ready = False
        chance = True
        starter = True
        member = 0
    else:
        ready, chance, starter, member = row

    # 3. STARTER bo‘lsa — 1 martalik test
    if starter:
        sql.execute("UPDATE referal SET starter = FALSE, chance = TRUE WHERE user_id = %s", (user_id,))
        db.commit()
        _, subject_code, subject_name = callback.data.split(":")
        await callback.message.answer("🧪 Sizga 1 martalik test imkoniyati berildi!")
        await start_subject(callback.message, state, subject_code, subject_name, duration=20 * 60)
        return

    # 4. CHANCE = TRUE va READY = FALSE bo‘lsa → referal taklif qilish
    if chance and not ready:
        await callback.message.answer(
            f"<b>Testdan to‘liq foydalanish uchun 3 ta do‘stingizni taklif qiling:</b>\n"
            f"https://t.me/BMB_testbot?start={user_id}\n\n"
            f"<b>Siz {member} ta do‘st taklif qilgansiz, yana {max(0, 3 - member)} ta kerak.</b>",
            parse_mode="HTML",
            reply_markup=await CheckData.share_link(user_id)
        )
        return

    # 5. READY = TRUE → to‘liq test ochiladi
    if ready:
        _, subject_code, subject_name = callback.data.split(":")
        if subject_code == "all":
            await callback.message.answer("✅ To‘liq test boshlandi (3 ta fan).")
            await start_all_subjects(callback.message, state)
        else:
            await callback.message.answer(f"✅ {subject_name} fanidan test boshlandi.")
            await start_subject(callback.message, state, subject_code, subject_name, duration=20 * 60)
        return


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
            print(photo)
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


@ques_router.callback_query(F.data.startswith("answer:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split(":")
    is_correct = data[2]
    index = int(data[3])
    score = float(data[4])
    subject = data[5]

    state_data = await state.get_data()
    end_time = state_data.get("end_time")
    if end_time is None:
        try:
            await callback.message.delete()
        except: pass
        await callback.message.answer("Eski so'rov bo'lishi mumkin!", reply_markup=await UserPanels.ques_manu())
        return
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
            insert_result(user_id=callback.from_user.id, subject={"Ona tili":"literature","Matematika":"math", "O‘zbekiston tarixi":"history"}[subject], number=info['correct'])
        result += f"\n\nUmumiy: {int((score + 0.01) // 1.1)} ta to‘g‘ri | {round(score, 1)} ball"
        result += f"\n⏳ {elapsed // 60} daqiqa {elapsed % 60} soniyada yakunlandi"

        await callback.message.answer(result, reply_markup=await UserPanels.ques_manu())
        try:
            await callback.message.delete()
        except: pass
        await state.clear()

def insert_result(user_id: int, subject: str, number: int):
    subject = subject.lower()
    if subject not in ["math", "literature", "history"]:
        raise ValueError("Noto‘g‘ri fan nomi!")

    query = f"""
        INSERT INTO results (user_id, {subject}, number)
        VALUES (%s, TRUE, %s)
    """
    cursor.execute(query, (user_id, number))
    conn.commit()


@ques_router.callback_query(F.data == "stop-quest")
async def stop_quiz(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Majburiy bloklardan test ishlash bo'limiga xush kelibsiz, kerakli fanni tanlang va davom eting!",
        parse_mode="html",
        reply_markup=await UserPanels.ques_manu()
    )
    await callback.message.delete()
