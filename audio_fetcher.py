import aiohttp
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
            print(f"🔐 Authenticating request for asset {asset_id}")
        else:
            print("⚠️ No .ROBLOSECURITY cookie set – using public access")

        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds
        print(f"📡 Fetching asset {asset_id}...")
        async with session.get(url, headers=headers, timeout=timeout) as resp:
            print(f"📡 Response status: {resp.status}")
            if resp.status != 200:
                raise Exception(f"Failed to fetch asset: HTTP {resp.status}")
            audio_data = await resp.read()
            print(f"📡 Downloaded {len(audio_data)} bytes")
            return audio_data

    async def analyze_audio(self, audio_data: bytes):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            audio = AudioSegment.from_file(tmp_path)
            duration = len(audio) / 1000.0
            sample_rate = audio.frame_rate
            sample_width = audio.sample_width
            bit_depth = sample_width * 8
            channels = audio.channels

            info = mediainfo(tmp_path)
            bitrate = info.get("bit_rate", "N/A")
            if bitrate != "N/A" and isinstance(bitrate, str):
                try:
                    bitrate_kbps = int(bitrate) // 1000
                    bitrate = f"{bitrate_kbps} kbps"
                except ValueError:
                    pass

            samples = audio.get_array_of_samples()
            max_val = 2 ** (bit_depth - 1)
            if len(samples) > 0:
                float_samples = [s / max_val for s in samples]
                rms = math.sqrt(sum(s**2 for s in float_samples) / len(float_samples))
                dbfs = 20 * math.log10(rms) if rms > 0 else -float('inf')
            else:
                dbfs = -float('inf')
                rms = 0

            lufs = 20 * math.log10(rms) - 0.691 if rms > 0 else -float('inf')

            num_points = 1000
            step = max(1, len(samples) // num_points)
            waveform = [samples[i] / max_val for i in range(0, len(samples), step)]

            return {
                "duration": round(duration, 2),
                "sample_rate": sample_rate,
                "bit_depth": bit_depth,
                "channels": channels,
                "bitrate": bitrate,
                "dbfs": round(dbfs, 2) if dbfs != -float('inf') else "N/A",
                "lufs": round(lufs, 2) if lufs != -float('inf') else "N/A",
                "waveform": waveform,
                "max_val": max_val
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def close(self):
        if self.session:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()