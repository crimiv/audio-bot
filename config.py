import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

MAIN_COOKIE = os.getenv(".ROBLOSECURITY")
UPLOAD_COOKIE = os.getenv(".ROBLOSECURITY_UPLOAD")