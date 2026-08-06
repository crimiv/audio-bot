import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAIN_COOKIE = os.getenv("ROBLOSECURITY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_cookie_list():
    cookies = []
    if MAIN_COOKIE:
        cookies.append(MAIN_COOKIE)
    i = 1
    while True:
        cookie = os.getenv(f"ROBLOSECURITY_{i}")
        if cookie:
            cookies.append(cookie)
            i += 1
        else:
            break
    return cookies