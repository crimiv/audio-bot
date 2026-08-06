import aiohttp
import asyncio
from config import SUPABASE_URL, SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("SUPABASE_URL and SUPABASE_KEY are required.")

BASE_URL = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

async def _request(method: str, table: str, data: dict = None, params: dict = None):
    async with aiohttp.ClientSession() as session:
        url = f"{BASE_URL}/{table}"
        async with session.request(method, url, headers=HEADERS, json=data, params=params) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise Exception(f"Supabase error {resp.status}: {text}")
            if resp.status == 204:
                return None
            return await resp.json()

async def get_user_cookie(user_id: str):
    params = {"user_id": f"eq.{user_id}"}
    result = await _request("GET", "user_cookies", params=params)
    if result and len(result) > 0:
        return result[0]["cookie"]
    return None

async def set_user_cookie(user_id: str, cookie: str):
    data = {"user_id": user_id, "cookie": cookie}
    await _request("POST", "user_cookies", data=data)

async def delete_user_cookie(user_id: str):
    params = {"user_id": f"eq.{user_id}"}
    await _request("DELETE", "user_cookies", params=params)

async def get_all_tracked_assets():
    result = await _request("GET", "tracking")
    return result if result else []

async def add_tracked_asset(asset_id: str, user_id: str):
    data = {"asset_id": asset_id, "user_id": user_id, "moderated": 0}
    await _request("POST", "tracking", data=data)

async def remove_tracked_asset(asset_id: str):
    params = {"asset_id": f"eq.{asset_id}"}
    await _request("DELETE", "tracking", params=params)

async def update_tracked_asset_moderated(asset_id: str, moderated: int):
    data = {"moderated": moderated}
    params = {"asset_id": f"eq.{asset_id}"}
    await _request("PATCH", "tracking", data=data, params=params)