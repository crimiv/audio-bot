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

        timeout = aiohttp.ClientTimeout(total=30)
        print(f"📡 Fetching asset {asset_id}...", flush=True)
        try:
            async with session.get(url, headers=headers, timeout=timeout) as resp:
                print(f"📡 Response status: {resp.status}", flush=True)
                content_type = resp.headers.get('Content-Type', '')
                print(f"📡 Content-Type: {content_type}", flush=True)

                audio_data = await resp.read()
                print(f"📡 Downloaded {len(audio_data)} bytes", flush=True)

                if 'application/json' in content_type:
                    try:
                        data = json.loads(audio_data)
                        if 'errors' in data and data['errors']:
                            error_msg = data['errors'][0].get('message', 'Unknown error')
                            raise Exception(f"Roblox API error: {error_msg}")
                        if 'location' in data:
                            location_url = data['location']
                            print(f"📡 Following CDN redirect to: {location_url}", flush=True)
                            # Stream download directly to a temp file to save memory
                            async with session.get(location_url, headers=headers, timeout=timeout) as cdn_resp:
                                if cdn_resp.status != 200:
                                    raise Exception(f"CDN returned HTTP {cdn_resp.status}")
                                # Write to temp file as we stream
                                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                                    tmp_path = tmp.name
                                    while True:
                                        chunk = await cdn_resp.content.read(8192)
                                        if not chunk:
                                            break
                                        tmp.write(chunk)
                                # Read the file back into memory (only if we need to, but we can just return the path)
                                # However, the rest of the code expects bytes. We'll read it, but we can also change analyze to accept a path.
                                # To minimize memory, we'll read the file into bytes only once.
                                with open(tmp_path, 'rb') as f:
                                    audio_data = f.read()
                                os.unlink(tmp_path)
                                print(f"📡 Downloaded {len(audio_data)} bytes from CDN", flush=True)
                                return audio_data
                        raise Exception(f"Roblox returned unexpected JSON: {json.dumps(data)[:200]}")
                    except json.JSONDecodeError:
                        pass

                if len(audio_data) < 1000:
                    try:
                        text = audio_data.decode('utf-8')
                        if '<html' in text.lower():
                            raise Exception("Roblox returned an HTML error page (invalid or private asset?)")
                        else:
                            raise Exception(f"Downloaded file is only {len(audio_data)} bytes – not a valid audio asset.")
                    except UnicodeDecodeError:
                        raise Exception(f"Downloaded file is only {len(audio_data)} bytes – not a valid audio asset.")

                return audio_data

        except asyncio.TimeoutError:
            print(f"❌ Request timed out after 30 seconds", flush=True)
            raise Exception("Request to Roblox timed out.")
        except Exception as e:
            print(f"❌ Request failed: {e}", flush=True)
            raise

    async def analyze_audio(self, audio_data: bytes):
        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        # Free the audio_data bytes early to reduce memory
        del audio_data
        gc.collect()

        try:
            # Load audio from file (pydub uses ffmpeg, may use lots of memory)
            audio = AudioSegment.from_file(tmp_path)
            duration = len(audio) / 1000.0
            sample_rate = audio.frame_rate
            sample_width = audio.sample_width
            bit_depth = sample_width * 8
            channels = audio.channels

            # Get bitrate
            info = mediainfo(tmp_path)
            bitrate = info.get("bit_rate", "N/A")
            if bitrate != "N/A" and isinstance(bitrate, str):
                try:
                    bitrate_kbps = int(bitrate) // 1000
                    bitrate = f"{bitrate_kbps} kbps"
                except ValueError:
                    pass

            # Get samples as array (this can be memory heavy)
            samples = audio.get_array_of_samples()
            max_val = 2 ** (bit_depth - 1)

            # Compute RMS
            if len(samples) > 0:
                # Use a simple sum of squares without converting to floats first
                sum_sq = sum(s * s for s in samples)
                rms = math.sqrt(sum_sq / len(samples)) / max_val
                dbfs = 20 * math.log10(rms) if rms > 0 else -float('inf')
            else:
                rms = 0
                dbfs = -float('inf')

            lufs = 20 * math.log10(rms) - 0.691 if rms > 0 else -float('inf')

            # Downsample waveform – reduce to 500 points to lower memory usage
            num_points = 500
            step = max(1, len(samples) // num_points)
            waveform = [samples[i] / max_val for i in range(0, len(samples), step)]

            # Free samples and audio object
            del samples
            del audio
            gc.collect()

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

        except CouldntDecodeError as e:
            raise Exception(f"Failed to decode audio. The downloaded file may not be a valid MP3. "
                            f"Check that the asset ID is correct and that the asset is playable audio. "
                            f"(Raw error: {str(e)[:200]})")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            gc.collect()

    async def close(self):
        if self.session:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()