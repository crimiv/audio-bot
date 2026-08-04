import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ROBLOX_ASSET_DELIVERY = "https://assetdelivery.roblox.com/v1/assetId"