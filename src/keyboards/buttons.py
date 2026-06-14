from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup

from config import sql, dp, bot, cursor, conn


class AdminPanel:
    @staticmethod
    async def admin_menu():
        btn=ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text="📊Statistika"),
                            KeyboardButton(text="🔧Kanallar"),
                        ],
                        [
                            KeyboardButton(text="🔧Adminlar👨‍💻"),
                            KeyboardButton(text="✍Xabarlar")
                        ],
                        [
                            KeyboardButton(text="📊Referallar"),
                            KeyboardButton(text="🔄 Referal tizimi"),
                        ]
                    ],
                    resize_keyboard=True,
                )
        return btn

    @staticmethod
    async def admin_channel():
        admin_channel=ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text="➕Kanal qo'shish"),
                            KeyboardButton(text="❌Kanalni olib tashlash"),
                        ],
                        [
                            KeyboardButton(text="📋 Kanallar ro'yxati"),
                            KeyboardButton(text="🔙Orqaga qaytish"),
                        ]
                    ],
                    resize_keyboard=True,
                )
        return admin_channel

    @staticmethod
    async def admin_anons():
        admin_message=ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text="📨Oddit forward"),
                            KeyboardButton(text="📬Oddiy xabar"),
                        ],
                        [
                            KeyboardButton(text="🔙Orqaga qaytish"),
                        ]
                    ],
                    resize_keyboard=True,
                )
        return admin_message

    @staticmethod
    async def admin_add():
        admin_channel=ReplyKeyboardMarkup(
                    keyboard=[
                        [
                            KeyboardButton(text="➕Admin qo'shish"),
                            KeyboardButton(text="❌Admin o'chirish"),
                        ],
                        [
                            KeyboardButton(text="📋 Adminlar ro'yxati"),
                            KeyboardButton(text="🔙Orqaga qaytish"),
                        ]
                    ],
                    resize_keyboard=True,
                )
        return admin_channel

    @staticmethod
    async def admin_msg():
        admin_channel = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📨Forward xabar yuborish"),
                    KeyboardButton(text="📬Oddiy xabar yuborish"),
                ],
                [
                    KeyboardButton(text="🧪Sinov: Copy yuborish"),
                    KeyboardButton(text="🧪Sinov: Forward yuborish")
                ],
                [
                    KeyboardButton(text="🔙Orqaga qaytish"),
                ]
            ],
            resize_keyboard=True,
        )
        return admin_channel


class UserPanels:
    @staticmethod
    async def join_btn(user_id):
        sql.execute("SELECT chat_id FROM public.mandatorys")
        rows = sql.fetchall()
        join_inline = []
        title = 1
        for row in rows:
            all_details = await bot.get_chat(chat_id=row[0])
            url = all_details.invite_link
            if not url:
                url = await bot.export_chat_invite_link(row[0])
            join_inline.append([InlineKeyboardButton(text=f"{title} - kanal", url=url)])
            title += 1
        join_inline.append([InlineKeyboardButton(text="✅Obuna bo'ldim", callback_data="check")])
        button = InlineKeyboardMarkup(inline_keyboard=join_inline)
        return button

    @staticmethod
    async def chance_manu():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📚 Majburiy blokdan test ishlash")
                ]
            ],
            resize_keyboard=True,
        )
        return btn

    @staticmethod
    async def ques_manu():
        btn = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="📝 Matematika️"),
                    KeyboardButton(text="📚 Ona tili")
                ],
                [
                    KeyboardButton(text="📚 Tarix"),
                    KeyboardButton(text="🧮 Hamasidan"),
                ],
                [
                    KeyboardButton(text="📊Natijalarim")
                ]
            ],
            resize_keyboard=True,
        )
        return btn

    # @staticmethod
    