import os

from aiogram import Bot
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, User, FSInputFile, Message

from config import sql, db, bot, ADMIN_ID


class CheckData:
    @staticmethod
    async def share_link(user_id):
        ref_link = f"https://t.me/BMB_testbot?start={user_id}"
        share_link = f"https://t.me/share/url?text=Salom! Men senga ajoyib test bot tavsiya qilaman&url={ref_link}"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Do‘stlarga ulashish", url=share_link)]
        ])

        return kb

    @staticmethod
    async def check_member(bot: Bot, user_id: int):
        sql.execute("SELECT chat_id, status FROM public.mandatorys")
        mandatory, status = sql.fetchall()
        if not mandatory:
            return True, []

        channels = []
        for chat_id in mandatory:
            if status[mandatory.index(chat_id)][0]:
                try:
                    r = await bot.get_chat_member(chat_id=chat_id[0], user_id=user_id)
                    if r.status == "left" and user_id not in ADMIN_ID:
                        channels.append(chat_id[0])
                    print(channels)
                except Exception as e:
                    print(f"Xatolik: {e}")
            else:
                channels.append(chat_id[0])
        return (len(channels) == 0), channels

    @staticmethod
    async def channels_btn(channels: list):
        keyboard = []
        for index, channel_id in enumerate(channels, 1):
            sql.execute("SELECT username FROM public.mandatorys WHERE chat_id=%s", (channel_id,))
            link = sql.fetchone()
            if link:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"📢 Kanal-{index}",
                        url=link[0]
                    )
                ])
        keyboard.append([InlineKeyboardButton(text="✅Qo'shildim", callback_data="check")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)


class PanelFunc:
    @staticmethod
    async def channel_add(chat_id, link):
        sql.execute(f"INSERT INTO public.mandatorys( chat_id, username ) VALUES({chat_id}, '{link}');")
        db.commit()

    @staticmethod
    async def channel_delete(id):
        sql.execute(f'''DELETE FROM public.mandatorys WHERE chat_id = '{id}' ''')
        db.commit()

    @staticmethod
    async def channel_list():
        sql.execute("SELECT chat_id, username, status from public.mandatorys")
        str = ''
        for row, status in sql.fetchall():
            chat_id = row[0]
            username = row[1]
            try:
                all_details = await bot.get_chat(chat_id=chat_id)
                title = all_details.title
                channel_id = all_details.id
                channel_id = row[1]
                info = all_details.description
                str += f"------------------------------------------------\nKanal useri: > @{all_details.username}\nKamal nomi: > {title}\nKanal id si: > {channel_id}\nKanal haqida: > {info}\n"
            except Exception as e:
                str += f"------------------------------------------------\nKanal useri: > @{username}\nKanal id si: > {chat_id}\n"
        return str

    @staticmethod
    async def admin_add(chat_id):
        sql.execute(f"INSERT INTO public.admins( user_id ) VALUES({chat_id});")
        db.commit()

    @staticmethod
    async def admin_delete(id):
        sql.execute(f'''DELETE FROM public.admins WHERE user_id = '{id}' ''')
        db.commit()

    @staticmethod
    async def admin_list():
        sql.execute("SELECT user_id from public.admins")
        str = ""
        for row in sql.fetchall():
            chat_id = row[0]
            try:
                user: User = await bot.get_chat(chat_id)
                username = f"@{user.username}" if user.username else "❌ Topilmadi"
                full_name = user.full_name
                str += f"👤 Foydalanuvchi:\n🔹 Ism: {full_name}\n🔹 Username: {username}\n🔹 ID: <code>{user.id}</code>\n\n"
            except Exception as e:
                str += f"xatolik:\n" + f"🔹 ID: <code>{chat_id}</code>\n\n"
        return str

def status_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tekshirish", callback_data=f"status_true:{channel_id}"),
            InlineKeyboardButton(text="❌ Tekshirmaslik", callback_data=f"status_false:{channel_id}")
        ]
    ])


class AdminFilter(BaseFilter):
    def __init__(self, static_admins: list[int]):
        self.static_admins = static_admins

    async def __call__(self, message: Message) -> bool:
        sql.execute("SELECT user_id FROM public.admins")
        db_admins = [int(row[0]) for row in sql.fetchall()]
        all_admins = set(db_admins + self.static_admins)
        return message.from_user.id in all_admins
