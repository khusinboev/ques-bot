import asyncio
import random
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from config import sql, db, bot
from src.keyboards.buttons import UserPanels
from src.keyboards.keyboard_func import CheckData
from src.handlers.users.questions import show_question

check_router = Router()

@check_router.message(F.text == "📚 Majburiy blokdan test ishlash")
async def show_start_buttons(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Boshlash", callback_data="start-checkup")]
    ])
    await message.answer(
        "📝 Majburiy fanlardan test ishlashni boshlash uchun quyidagi tugmani bosing:",
        reply_markup=keyboard
    )

@check_router.callback_query(F.data == "start-checkup")
async def start_checkup(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    # Kanalga a'zo bo‘lganini tekshir
    check_status, channels = await CheckData.check_member(bot, user_id)
    if not check_status:
        await callback.message.delete()
        await callback.message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                                      reply_markup=await CheckData.channels_btn(channels))
        return

    # referal statusni tekshiramiz
    sql.execute("SELECT chance, ready FROM referal WHERE user_id = %s", (user_id,))
    row = sql.fetchone()

    if not row:
        # Birinchi marta test qilayotgan foydalanuvchi
        sql.execute("INSERT INTO referal (user_id, chance, ready, member, starter) VALUES (%s, TRUE, FALSE, 0, TRUE)", (user_id,))
        db.commit()
        chance, ready = True, False
    else:
        chance, ready = row

    if not chance:
        await callback.message.answer("🚫 Sizda test ishlash imkoniyati yo‘q.", reply_markup=await UserPanels.chance_manu())
        return

    if ready:
        await callback.message.answer("✅ Sizda to‘liq test ishlash ruxsati bor.", reply_markup=await UserPanels.ques_manu())
        return

    # 1 martalik testni boshlaymiz
    await run_checkup_test(callback, state)

async def run_checkup_test(callback: CallbackQuery, state: FSMContext):
    subjects = [("literature", "Ona tili"), ("math", "Matematika"), ("history", "O‘zbekiston tarixi")]
    selected_all = []
    stats = {}

    for table_name, subject_name in subjects:
        sql.execute(f"SELECT DISTINCT varyant FROM {table_name} WHERE status='True'")
        variants = sql.fetchall()
        if not variants:
            await callback.message.answer(f"{subject_name} fanida variant topilmadi.")
            return
        selected_variant = random.choice([v[0] for v in variants])
        sql.execute(f"SELECT file_id, answer FROM {table_name} WHERE varyant = %s AND status = 'True'", (selected_variant,))
        questions = sql.fetchall()
        if len(questions) < 10:
            await callback.message.answer(f"{subject_name} fanida {selected_variant}-variantda test yetarli emas.")
            return
        sample = random.sample(questions, 10)
        selected_all.extend([(q[0], q[1], subject_name) for q in sample])
        stats[subject_name] = {'correct': 0, 'score': 0.0}

    start_time = asyncio.get_event_loop().time()
    end_time = start_time + 60 * 60  # 1 soat

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
    await callback.message.answer("📚 1 martalik majburiy test boshlandi.", reply_markup=ReplyKeyboardRemove())
    await show_question(callback, selected_all[0], 0, 0.0, state)