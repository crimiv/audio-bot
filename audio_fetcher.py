import aiohttp
import asyncio
import tempfile
import os
import math
from pydub import AudioSegment
from pydub.utils import mediainfo
from config import ROBLOX_SECURITY

class RobloxAudioFetcher:
    def __init__(self):
        self.session = None

    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def fetch_audio(self, asset_id: int):
        session = await self._get_session()
        url = f"https://assetdelivery.roblox.com/v1/assetId/{asset_id}"
        headers = {}
        if ROBLOX_SECURITY:
            headers['Cookie'] = f'.ROBLOSECURITY={ROBLOX_SECURITY}'
            print(f"🔐 Authenticating request for asset {asset_id}", flush=True)
        else:
            print("⚠️ No .ROBLOSECURITY cookie set – using public access", flush=True)

        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds
        print(f"📡 Fetching asset {asset_id}...", flush=True)
        try:
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                print(f"📡 Response status: {resp.status}", flush=True)
                if resp.status != 200:
                    raise Exception(f"Failed to fetch asset: HTTP {resp.status}")
                audio_data = await resp.read()
                print(f"📡 Downloaded {len(audio_data)} bytes", flush=True)
                return audio_data
        except asyncio.TimeoutError:
            print(f"❌ Request timed out after 30 seconds for asset {asset_id}", flush=True)
            raise Exception("Request to Roblox timed out. The asset may be too large or the server is slow.")
        except Exception as e:
            print(f"❌ Request failed: {e}", flush=True)
            raise