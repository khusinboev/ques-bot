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

    # 1. Kanalga a'zo bo'lganligini tekshirish
    check_status, channels = await CheckData.check_member(bot, user_id)
    if not check_status:
        await callback.message.delete()
        await callback.message.answer("❗ Iltimos, quyidagi kanallarga a’zo bo‘ling:",
                                      reply_markup=await CheckData.channels_btn(channels))
        return

    # 2. referal jadvalidan ma'lumot olish
    sql.execute("SELECT chance, ready, starter, member FROM referal WHERE user_id = %s", (user_id,))
    row = sql.fetchone()

    if not row:
        # Foydalanuvchi birinchi marta kirgan — jadvalga qo'shamiz
        sql.execute("""
            INSERT INTO referal (user_id, chance, ready, starter, member)
            VALUES (%s, FALSE, FALSE, TRUE, 0)
        """, (user_id,))
        db.commit()
        starter = True
        chance = False
        ready = False
        member = 0
    else:
        chance, ready, starter, member = row

    # 3. Agar starter True bo‘lsa — 1-martalik testga ruxsat
    if starter:
        sql.execute("UPDATE referal SET starter = FALSE, chance = TRUE WHERE user_id = %s", (user_id,))
        db.commit()
        await run_checkup_test(callback, state)
        return

    # 4. Agar member >= 3 bo‘lsa — to‘liq ruxsat beriladi
    if member >= 3:
        sql.execute("UPDATE referal SET ready = TRUE, chance = FALSE WHERE user_id = %s", (user_id,))
        db.commit()
        await callback.message.answer("✅ Sizga testlarni to‘liq ishlash imkoniyati taqdim etildi!",
                                      reply_markup=await UserPanels.ques_manu())
        return

    # 5. Agar chance True, lekin ready hali emas — referal taklifi yuboriladi
    if chance and not ready:
        await callback.message.answer(
            f"<b>Testdan to‘liq foydalanish uchun 3 ta do‘stingizni taklif qiling:</b>\n"
            f"https://t.me/BMB_testbot?start={user_id}\n\n"
            f"<i>Siz {member} ta do‘st taklif qilgansiz. Yana {3 - member} ta kerak.</i>",
            parse_mode="HTML",
            reply_markup=await CheckData.share_link(user_id)
        )
        return

    # 6. Hech qanday imkon yo‘q
    await callback.message.answer("🚫 Sizda test ishlash ruxsati mavjud emas.",
                                  reply_markup=await UserPanels.chance_manu())


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