import asyncio
import logging
from typing import List

import click
from aiogram.utils.exceptions import Unauthorized
from aiogram.utils.executor import start_polling

from src.db import get_users, get_username, add_user, update_user, remove_user, redis
from src.defines import bot, dp
import src.bot
from src.worker import start_worker


async def add_impl(uids: List[int]):
    for uid in uids:
        if uid in await get_users():
            print(f'{uid} is already a user')
        else:
            try:
                m = await bot.send_message(uid, 'Добро пожаловать. Снова.')
                await add_user(uid)
                await update_user(m.chat)
                print(f'{m.chat.full_name} [{uid}] was added')
            except Unauthorized:
                print(f'Can\'t send a message to {uid}')
    await redis.close()
    await (await bot.get_session()).close()


async def remove_impl(uid: int):
    if uid not in await get_users():
        print('Not a user')
    else:
        username = await get_username(uid)
        await remove_user(int(uid))
        print(f'{username} [{uid}] was removed')
    await redis.close()


async def list_users_impl():
    users = await get_users()
    print(f'Total: {users}')
    for uid in users:
        username = await get_username(uid)
        print(f' - [{uid:>15}] {username}')


@click.group()
def cli():
    pass


@cli.command()
def start():
    logging.basicConfig(level=logging.INFO)
    start_polling(dp, skip_updates=True, on_startup=start_worker)


@cli.command()
@click.argument('uids', nargs=-1, type=int)
def add(uids: List[int]):
    asyncio.get_event_loop().run_until_complete(add_impl(uids))


@cli.command()
@click.argument('uid', type=int)
def remove(uid: int):
    asyncio.get_event_loop().run_until_complete(remove_impl(uid))


@cli.command(name='list')
def list_users():
    asyncio.get_event_loop().run_until_complete(list_users_impl())
