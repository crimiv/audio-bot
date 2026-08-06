from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("SUPABASE_URL and SUPABASE_KEY are required.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_cookie(user_id: str):
    resp = supabase.table("user_cookies").select("cookie").eq("user_id", user_id).execute()
    if resp.data and len(resp.data) > 0:
        return resp.data[0]["cookie"]
    return None

def set_user_cookie(user_id: str, cookie: str):
    supabase.table("user_cookies").upsert({"user_id": user_id, "cookie": cookie}).execute()

def delete_user_cookie(user_id: str):
    supabase.table("user_cookies").delete().eq("user_id", user_id).execute()

def get_all_tracked_assets():
    resp = supabase.table("tracking").select("*").execute()
    return resp.data if resp.data else []

def add_tracked_asset(asset_id: str, user_id: str):
    supabase.table("tracking").upsert({"asset_id": asset_id, "user_id": user_id, "moderated": 0}).execute()

def remove_tracked_asset(asset_id: str):
    supabase.table("tracking").delete().eq("asset_id", asset_id).execute()

def update_tracked_asset_moderated(asset_id: str, moderated: int):
    supabase.table("tracking").update({"moderated": moderated}).eq("asset_id", asset_id).execute()