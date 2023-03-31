import asyncio
import logging
import re
from asyncio import sleep, QueueEmpty
from html import escape
from time import time
from typing import List, Dict, Any

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode, MediaGroup, \
    ContentType, ChatType
from aiogram.utils.exceptions import Unauthorized, BadRequest
from aiogram.utils.parts import MAX_MESSAGE_LENGTH

from src.defines import MANAGEMENT_CHAT, bot, mq
from src.db import get_users, last_media, update_last_media, get_counter_by_mid, get_mid_by_counter, update_user, \
    save_sent_mid, get_username, get_link, remove_user, increase_counter, antispam, get_flag, set_flag
from src.utils import build_link, notify_add_request


def sign_text(m: Message):
    try:
        text = m.html_text
    except TypeError:
        text = ''
    text = re.sub(r'</?tg-emoji.*?>', '', text)
    sign = ''
    suffix = ' 🦝'
    if not text.startswith('/unsign'):
        sign = f'\n\n<a href="{build_link(m.chat)}">{escape(m.chat.full_name)}</a>'
    elif text.startswith('/unsign'):
        text = text[7:]
    elif text.startswith('/sing'):
        if text:
            text = '♪~' + text[5:]
        suffix = ' ~♪'
    if m.media_group_id and m.is_forward():
        if m.forward_from_chat:
            sign += f'\n\nПереслано из <a href="{build_link(m.forward_from_chat)}">{m.forward_from_chat.full_name}</a>'
        else:
            sign += f'\n\nПереслано от <a href="{build_link(m.forward_from)}">{m.forward_from.full_name}</a>'
    if len(text + sign) > (MAX_MESSAGE_LENGTH if m.text else 1024):
        text = text[:-(len(sign) + 1)]
    text = text + (suffix if text else '') + sign
    return text


async def validate_user(m: Message):
    users = await get_users()
    uid = m.chat.id
    if uid not in users:
        await notify_add_request(m.chat)
        await m.reply('Ты кто такой?')
        return None
    return users


async def process_message(m: Message):
    if not hasattr(m, 'is_forward'):
        return

    uid = m.chat.id

    if m.sticker or m.animation:
        delta = time() - await last_media(uid)
        if delta < 15:
            await m.reply(f'Не вайпи еще {round(15 - delta)} секунд')
            return
        await update_last_media(uid)

    users = await validate_user(m)
    if not users:
        return

    if not await get_flag(m.chat.id, '1apr23'):
        await m.reply('Сегодня твой день, енот! '
                      'Сегодня все сообщения будут подписываться, если не начинать их с /unsign. '
                      'Предупреждаю только один раз.')
        await set_flag(m.chat.id, '1apr23', True)
        return

    text = sign_text(m)

    mid = m.reply_to_message and await get_counter_by_mid(m.chat.id, m.reply_to_message.message_id)

    func = None
    args = []
    kwargs = {}
    hash_args = []
    if m.is_forward():
        func = m.forward
    elif hasattr(m, 'audio') and m.audio:
        a = m.audio
        func = bot.send_audio()
        args = [a.file_id, text, ParseMode.HTML, a.duration, a.performer, a.title]
    elif hasattr(m, 'document') and m.document:
        d = m.document
        func = bot.send_document
        args = [d.file_id, d.thumb and d.thumb.file_id, text, ParseMode.HTML]
    elif hasattr(m, 'photo') and m.photo:
        p = m.photo
        func = bot.send_photo
        args = [p[-1].file_id, text, ParseMode.HTML]
        hash_args = [p[-1].file_unique_id, text]
    elif hasattr(m, 'sticker') and m.sticker:
        s = m.sticker
        func = bot.send_sticker
        args = [s.file_id]
    elif hasattr(m, 'video') and m.video:
        v = m.video
        func = bot.send_video
        args = [v.file_id, v.duration, v.width, v.height, v.thumb and v.thumb.file_id, text, ParseMode.HTML]
    elif hasattr(m, 'voice') and m.voice:
        v = m.voice
        func = bot.send_voice
        args = [v.file_id, text, ParseMode.HTML, None, v.duration]
    elif hasattr(m, 'video_note') and m.video_note:
        vn = m.video_note
        func = bot.send_video_note
        args = [vn.file_id, vn.duration, vn.length, vn.thumb and vn.thumb.file_id]
    elif hasattr(m, 'contact') and m.contact:
        c = m.contact
        func = bot.send_contact
        args = [c.phone_number, c.first_name, c.last_name, c.vcard]
    elif hasattr(m, 'location') and m.location:
        l = m.location
        func = bot.send_location
        args = [l.latitude, l.longitude]
    elif hasattr(m, 'venue') and m.venue:
        v = m.venue
        l = v.location
        func = bot.send_venue
        args = [l.latitude, l.longitude, v.title, v.address, v.foursquare_id]
    elif hasattr(m, 'text') and m.text:
        func = bot.send_message
        args = [text, ParseMode.HTML]

    if not await antispam(hash_args or args):
        await m.reply('Не вайпи')
        return

    for sub_id in users:
        await sleep(.02)

        reply_to_message_id = mid and await get_mid_by_counter(sub_id, mid)

        try:
            if reply_to_message_id:
                kwargs['reply_to_message_id'] = reply_to_message_id
                kwargs['allow_sending_without_reply'] = True
            m = await func(sub_id, *args, **kwargs)

            await save_sent_mid(sub_id, m.message_id)
        except Unauthorized:
            removed_username = await get_username(sub_id)
            removed_link = await get_link(sub_id)
            await remove_user(sub_id)
            await bot.send_message(MANAGEMENT_CHAT, f'<a href="{removed_link}">{removed_username}</a> был удален '
                                                    f'из-за блокировки бота', parse_mode=ParseMode.HTML)
        except BadRequest as e:
            logging.exception(e)

    await increase_counter()


async def process_message_group(mg: List[Message]):
    m = mg[0]
    uid = m.chat.id

    users = await validate_user(m)
    if not users:
        return

    mid = m.reply_to_message and await get_counter_by_mid(uid, m.reply_to_message.message_id)

    media_group = MediaGroup()
    for i, message in enumerate(mg):
        caption = None if i != 0 else sign_text(message)

        if message.content_type == ContentType.PHOTO:
            media_group.attach_photo(message.photo[-1].file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.content_type == ContentType.VIDEO:
            media_group.attach_video(message.video.file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.content_type == ContentType.DOCUMENT:
            media_group.attach_document(message.document.file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.content_type == ContentType.AUDIO:
            media_group.attach_audio(message.audio.file_id, caption=caption, parse_mode=ParseMode.HTML)

    for sub_id in users:
        await sleep(.02)

        reply_to_message_id = mid and await get_mid_by_counter(sub_id, mid)

        try:
            sms = await bot.send_media_group(sub_id, media_group,
                                             reply_to_message_id=reply_to_message_id)
            for i, sm in enumerate(sms):
                await save_sent_mid(sub_id, sm.message_id, i)
            await update_user(sms[0].chat)
        except Unauthorized:
            removed_username = await get_username(sub_id)
            removed_link = await get_link(sub_id)
            await remove_user(sub_id)
            await bot.send_message(MANAGEMENT_CHAT, f'<a href="{removed_link}">{removed_username}</a> был удален '
                                                    f'из-за блокировки бота', parse_mode=ParseMode.HTML)
    await increase_counter(len(media_group.media))


async def process_queue_item(m: Message):
    if m.media_group_id:
        media_group = []
        mg_id = m.media_group_id
        while m.media_group_id == mg_id:
            media_group.append(m)
            try:
                m = mq.get_nowait()
            except QueueEmpty:
                m = None
                break
        await process_message_group(media_group)
        if m:
            await process_queue_item(m)
    else:
        await process_message(m)


async def message_worker():
    logging.basicConfig(level=logging.INFO)
    while True:
        message = await mq.get()
        try:
            await process_queue_item(message)
        except Exception as e:
            logging.exception(e)


async def start_worker(_):
    asyncio.get_event_loop().create_task(message_worker())
