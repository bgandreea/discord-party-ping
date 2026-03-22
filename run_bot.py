import os
from dotenv import load_dotenv

from utilities.ping_server import run_bot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing. Add it to your .env file.")

print("Token loaded:", bool(BOT_TOKEN))
run_bot(BOT_TOKEN)