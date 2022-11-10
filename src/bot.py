import logging
from html import escape

from aiogram.dispatcher.filters import ChatTypeFilter, IDFilter, Regexp
from aiogram.types import ChatType, Message, ParseMode, CallbackQuery, ContentType

from src.db import get_users, remove_user, add_user, update_user, get_username, get_link
from src.defines import MANAGEMENT_CHAT, bot, dp, mq
from src.utils import notify_add_request


@dp.message_handler(ChatTypeFilter(ChatType.PRIVATE), commands='start')
async def start_command(message: Message):
    subs = await get_users()
    if message.chat.id in subs:
        await message.reply('Ну и что?')
    else:
        await notify_add_request(message.chat)
        await message.reply('Туда -> @lono_contactbot')


@dp.message_handler(ChatTypeFilter(ChatType.PRIVATE), commands='stop')
async def stop_command(message: Message):
    await remove_user(int(message.chat.id))
    await message.reply('Ну и уходи')


@dp.message_handler(IDFilter(MANAGEMENT_CHAT), commands='add')
async def add_command(message: Message):
    args = message.get_args()
    if args:
        uid = args
    elif message.reply_to_message:
        uid = message.reply_to_message.from_user.id
    else:
        await message.reply('Укажите ID пользователя или ответьте на его сообщение')
        return

    m = await bot.send_message(uid, 'Добро пожаловать. Снова.')
    await add_user(uid)
    await update_user(m.chat)
    username = await get_username(uid)
    await message.reply(f'<a href="{await get_link(uid)}">{escape(username)}</a> [{uid}] был добавлен',
                        parse_mode=ParseMode.HTML)


@dp.callback_query_handler(Regexp(r'^add (\d+)$'))
async def add_callback(callback_query: CallbackQuery):
    uid = int(callback_query.data.split()[1])

    m = await bot.send_message(uid, 'Добро пожаловать. Снова.')
    await update_user(m.chat)
    await add_user(uid)
    username = await get_username(uid)
    await callback_query.message.edit_text(f'<a href="{await get_link(uid)}">{escape(username)}</a> [{uid}] был добавлен',
                                           parse_mode=ParseMode.HTML)


@dp.message_handler(IDFilter(MANAGEMENT_CHAT), commands='remove')
async def remove_command(message: Message):
    args = message.get_args()
    if args:
        uid = args
    elif message.reply_to_message:
        uid = message.reply_to_message.from_user.id
    else:
        await message.reply('Укажите ID пользователя или ответьте на его сообщение')
        return

    username = await get_username(uid)
    if not username:
        await message.reply(f'Пользователь id={uid} не был найден')
        return
    link = await get_link(uid)
    await remove_user(int(uid))
    await message.reply(f'<a href="{link}">{escape(username)}</a> [{uid}] был удален',
                        parse_mode=ParseMode.HTML)


@dp.callback_query_handler(Regexp(r'^remove (\d+)$'))
async def remove_callback(callback_query: CallbackQuery):
    uid = int(callback_query.data.split()[1])
    username = await get_username(uid)
    if not username:
        await callback_query.message.reply(f'Пользователь id={uid} не был найден')
        return
    link = await get_link(uid)
    await remove_user(uid)
    await callback_query.message.reply(f'<a href="{link}">{escape(username)}</a> [{uid}] был удален',
                                       parse_mode=ParseMode.HTML)
    await callback_query.message.edit_reply_markup()


@dp.message_handler(ChatTypeFilter(ChatType.PRIVATE), commands='users')
async def users_command(message: Message):
    subs = await get_users()

    if message.chat.id not in subs:
        return

    messages = [f'Count: {len(subs)}\n']
    for uid in subs:
        msg = f'<code>{uid:>14}</code> '
        username = await get_username(uid)
        if uid < 0:
            msg += username
        else:
            msg += f'<a href="{await get_link(uid)}">{username}</a>'
        messages.append(msg)

    for i in range(0, len(messages), 40):
        await message.reply("\n".join(messages[i:i + 40]), parse_mode=ParseMode.HTML)


@dp.message_handler(ChatTypeFilter(ChatType.PRIVATE), content_types=ContentType.all())
async def message_handler(message: Message):
    await mq.put(message)
