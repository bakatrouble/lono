import os
from asyncio import Queue

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

MANAGEMENT_CHAT = int(os.environ['MANAGEMENT_CHAT'])
bot = Bot(token=os.environ['BOT_TOKEN'])
dp = Dispatcher(bot)
mq: Queue[Message] = Queue()
