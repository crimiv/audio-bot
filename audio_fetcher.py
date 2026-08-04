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
        """
        Downloads the audio asset and returns a tuple (audio_bytes, file_size).
        For large files, we stream to a temp file and then return bytes.
        """
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

                # Read initial response (might be JSON)
                initial_data = await resp.read()
                print(f"📡 Downloaded {len(initial_data)} bytes", flush=True)

                # Handle JSON response (usually contains a location URL)
                if 'application/json' in content_type:
                    try:
                        data = json.loads(initial_data)
                        if 'errors' in data and data['errors']:
                            error_msg = data['errors'][0].get('message', 'Unknown error')
                            raise Exception(f"Roblox API error: {error_msg}")
                        if 'location' in data:
                            location_url = data['location']
                            print(f"📡 Following CDN redirect to: {location_url}", flush=True)
                            # Stream the CDN file to a temp file
                            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                                tmp_path = tmp.name
                                async with session.get(location_url, headers=headers, timeout=timeout) as cdn_resp:
                                    if cdn_resp.status != 200:
                                        raise Exception(f"CDN returned HTTP {cdn_resp.status}")
                                    while True:
                                        chunk = await cdn_resp.content.read(8192)
                                        if not chunk:
                                            break
                                        tmp.write(chunk)
                            # Read the file into bytes (we need bytes for analyze_audio)
                            with open(tmp_path, 'rb') as f:
                                audio_data = f.read()
                            os.unlink(tmp_path)
                            print(f"📡 Downloaded {len(audio_data)} bytes from CDN", flush=True)
                            return audio_data
                        else:
                            raise Exception(f"Unexpected JSON: {json.dumps(data)[:200]}")
                    except json.JSONDecodeError:
                        # Not JSON – maybe it's already audio
                        pass

                # If we get here, we have raw audio data (or an error page)
                if len(initial_data) < 1000:
                    try:
                        text = initial_data.decode('utf-8')
                        if '<html' in text.lower():
                            raise Exception("Roblox returned an HTML error page – invalid or private asset?")
                        else:
                            raise Exception(f"Downloaded file is only {len(initial_data)} bytes – not a valid audio asset.")
                    except UnicodeDecodeError:
                        raise Exception(f"Downloaded file is only {len(initial_data)} bytes – not a valid audio asset.")

                # It's audio – return the bytes
                return initial_data

        except asyncio.TimeoutError:
            print(f"❌ Request timed out after 30 seconds", flush=True)
            raise Exception("Request to Roblox timed out.")
        except Exception as e:
            print(f"❌ Request failed: {e}", flush=True)
            raise

    async def analyze_audio(self, audio_data: bytes):
        """
        Analyze audio bytes and return metadata.
        """
        # Write to a temporary file for pydub
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        # Free the bytes object to reduce memory
        del audio_data
        gc.collect()

        try:
            # Load audio from file
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

            # Get samples as array
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

            # Reduce waveform points to 400 to save memory
            num_points = 400
            step = max(1, len(samples) // num_points)
            waveform = [samples[i] / max_val for i in range(0, len(samples), step)]

            # Free large objects
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
            raise Exception(f"Failed to decode audio. The file may not be a valid MP3. "
                            f"Error: {str(e)[:200]}")
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