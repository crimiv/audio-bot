import aiohttp
import asyncio
import tempfile
import os
import math
import json
import gc
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pydub.utils import mediainfo
from config import ROBLOX_SECURITY

MAX_AUDIO_SIZE = 8 * 1024 * 1024

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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if ROBLOX_SECURITY:
            headers['Cookie'] = f'.ROBLOSECURITY={ROBLOX_SECURITY}'

        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                content_type = resp.headers.get('Content-Type', '')
                initial_data = await resp.read()

                if 'application/json' in content_type:
                    try:
                        data = json.loads(initial_data)
                        if 'errors' in data and data['errors']:
                            error_msg = data['errors'][0].get('message', 'Unknown error')
                            raise Exception(f"Roblox API error: {error_msg}")
                        if 'location' in data:
                            location_url = data['location']
                            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                                tmp_path = tmp.name
                                async with session.get(location_url, headers=headers, timeout=timeout) as cdn_resp:
                                    if cdn_resp.status != 200:
                                        raise Exception(f"CDN returned HTTP {cdn_resp.status}")
                                    bytes_downloaded = 0
                                    while True:
                                        chunk = await cdn_resp.content.read(8192)
                                        if not chunk:
                                            break
                                        bytes_downloaded += len(chunk)
                                        if bytes_downloaded > MAX_AUDIO_SIZE:
                                            raise Exception(f"Audio file exceeds maximum size of {MAX_AUDIO_SIZE//1024//1024} MB")
                                        tmp.write(chunk)
                            with open(tmp_path, 'rb') as f:
                                audio_data = f.read()
                            os.unlink(tmp_path)
                            return audio_data
                        else:
                            raise Exception(f"Unexpected JSON: {json.dumps(data)[:200]}")
                    except json.JSONDecodeError:
                        pass

                if len(initial_data) < 1000:
                    try:
                        text = initial_data.decode('utf-8')
                        if '<html' in text.lower():
                            raise Exception("Roblox returned an HTML error page")
                        else:
                            raise Exception(f"Downloaded file is only {len(initial_data)} bytes")
                    except UnicodeDecodeError:
                        raise Exception(f"Downloaded file is only {len(initial_data)} bytes")

                return initial_data

        except asyncio.TimeoutError:
            raise Exception("Request to Roblox timed out.")
        except Exception as e:
            raise

    async def analyze_audio(self, audio_data: bytes):
        if len(audio_data) > MAX_AUDIO_SIZE:
            raise Exception(f"Audio file too large: {len(audio_data)//1024//1024} MB (max {MAX_AUDIO_SIZE//1024//1024} MB)")

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        del audio_data
        gc.collect()

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
                sum_sq = sum(s * s for s in samples)
                rms = math.sqrt(sum_sq / len(samples)) / max_val
                dbfs = 20 * math.log10(rms) if rms > 0 else -float('inf')
            else:
                rms = 0
                dbfs = -float('inf')

            lufs = 20 * math.log10(rms) - 0.691 if rms > 0 else -float('inf')

            waveform = self._compute_waveform_rms(samples, max_val, num_points=400)

            del samples
            del audio
            gc.collect()

            return {
                "duration": duration,
                "sample_rate": sample_rate,
                "bit_depth": bit_depth,
                "channels": channels,
                "bitrate": bitrate,
                "dbfs": round(dbfs, 2) if dbfs != -float('inf') else "N/A",
                "lufs": round(lufs, 2) if lufs != -float('inf') else "N/A",
                "waveform": waveform,
                "max_val": max_val
            }

        except CouldntDecodeError as e:
            raise Exception(f"Failed to decode audio: {str(e)[:200]}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            gc.collect()

    def _compute_waveform_rms(self, samples, max_val, num_points=400):
        if not samples:
            return []
        block_size = max(1, len(samples) // num_points)
        waveform = []
        for i in range(0, len(samples), block_size):
            block = samples[i:i+block_size]
            if block:
                rms = math.sqrt(sum(s*s for s in block) / len(block)) / max_val
                waveform.append(rms)
        return waveform

    async def close(self):
        if self.session:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()