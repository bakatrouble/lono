from hashlib import sha1
from time import time
from typing import List

import aioredis
from aiogram.types import Chat

from src.utils import build_link

redis = aioredis.from_url('redis://localhost')


async def get_users():
    return [int(uid.decode()) for uid in await redis.smembers('lono:users')]


async def add_user(uid: int):
    await redis.sadd('lono:users', uid)


async def remove_user(uid: int):
    await redis.srem('lono:users', uid)
    await redis.delete(f'lono:usernames:{uid}')
    await redis.delete(f'lono:links:{uid}')


async def update_user(chat: Chat):
    await redis.set(f'lono:usernames:{chat.id}', chat.full_name)
    await redis.set(f'lono:links:{chat.id}', build_link(chat))


async def get_username(uid: int):
    return (await redis.get(f'lono:usernames:{uid}') or b'').decode() or '<username not recorded>'


async def get_link(uid: int):
    return (await redis.get(f'lono:links:{uid}') or b'').decode() or f'tg://user?id={uid}'


async def last_media(uid: int):
    return int((await redis.get(f'lono:last_media:{uid}') or b'0').decode()) or 0


async def update_last_media(uid: int):
    await redis.set(f'lono:last_media:{uid}', int(time()))


async def increase_counter(delta: int = 1):
    await redis.incr('lono:counter', delta)


async def get_counter():
    return int((await redis.get('lono:counter') or b'0').decode())


async def save_sent_mid(uid: int, mid: int, offset: int = 0):
    counter = await get_counter() + offset
    await redis.set(f'lono:mid:{uid}:{counter}', mid)
    await redis.set(f'lono:mid_r:{uid}:{mid}', counter)


async def get_mid_by_counter(uid: int, counter: int):
    return int((await redis.get(f'lono:mid:{uid}:{counter}') or b'0').decode())


async def get_counter_by_mid(uid: int, mid: int):
    return int((await redis.get(f'lono:mid_r:{uid}:{mid}') or b'0').decode())


async def antispam(args: List[any]):
    if not args:
        return True
    args = '|'.join(map(str, args))
    digest = sha1(args.encode()).digest()
    key = f'lono:antispam:{digest.hex()}'
    if await redis.get(key):
        return False
    await redis.set(key, '1', ex=30)
    return True


async def get_flag(uid: int, flag: str):
    return bool(await redis.hget(f'lono:flags:{uid}', flag))


async def set_flag(uid: int, flag: str, value: bool):
    if value:
        await redis.hset(f'lono:flags:{uid}', flag, '1')
    else:
        await redis.hdel(f'lono:flags:{uid}', flag)

