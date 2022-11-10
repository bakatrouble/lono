from html import escape
from typing import Union

from aiogram.types import Chat, User, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode

from src.defines import bot, MANAGEMENT_CHAT


def build_link(chat: Union[Chat, User]):
    if chat.username:
        return f'tg://resolve?domain={chat.username}'
    else:
        return f'tg://user?id={chat.id}'


async def notify_add_request(c: Chat):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton('Добавить', callback_data=f'add {c.id}'))
    await bot.send_message(MANAGEMENT_CHAT,
                           f'<a href="{build_link(c)}">{escape(c.full_name)}</a> [{c.id}] запросил доступ',
                           parse_mode=ParseMode.HTML, reply_markup=markup)
