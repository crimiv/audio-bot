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
from config import MAIN_COOKIE, UPLOAD_COOKIE

MAX_AUDIO_SIZE = 8 * 1024 * 1024

class RobloxAudioFetcher:
    def __init__(self):
        self.session = None

    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def fetch_asset_details(self, asset_id: int, cookie: str = None):
        session = await self._get_session()
        url = f"https://economy.roblox.com/v2/assets/{asset_id}/details"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if cookie:
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data:
                    creator = data.get("Creator", {})
                    creator_name = creator.get("Name", "Unknown")
                    if not creator_name or creator_name == "":
                        creator_name = "Unknown"
                    return {
                        "name": creator_name,
                        "creator_id": creator.get("Id"),
                        "creator_type": creator.get("Type"),
                        "favorite_count": data.get("FavoritedCount", 0),
                        "created": data.get("Created", None),
                        "description": data.get("Description", ""),
                        "genre": data.get("Genre", "")
                    }
                return None
        except:
            return None

    async def fetch_asset_moderation_status(self, asset_id: int, cookie: str = None):
        session = await self._get_session()
        url = f"https://economy.roblox.com/v2/assets/{asset_id}/details"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if cookie:
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'

        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return {"moderated": False, "status": "Active"}
                elif resp.status == 404 or resp.status == 403:
                    return {"moderated": True, "status": "Moderated or Deleted"}
                return {"moderated": False, "status": "Unknown"}
        except:
            return {"moderated": False, "status": "Error"}

    async def upload_audio(self, file_bytes: bytes, filename: str, name: str = None, description: str = None, group_id: int = None, cookie: str = None):
        if not cookie:
            raise Exception(".ROBLOSECURITY cookie is required for uploads.")

        session = await self._get_session()

        if not name:
            name = os.path.splitext(filename)[0]

        # Use the correct Roblox upload endpoint
        url = "https://assetdelivery.roblox.com/v1/asset"

        # Build the multipart form data
        data = aiohttp.FormData()
        data.add_field('assetType', 'Audio')
        data.add_field('name', name)
        if description:
            data.add_field('description', description)
        if group_id:
            data.add_field('groupId', str(group_id))
        # The file field must be named 'file' and include the content type
        data.add_field('file', file_bytes, filename=filename, content_type='audio/mpeg')

        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        try:
            async with session.post(url, data=data, headers=headers) as resp:
                result = await resp.text()
                print(f"Upload response status: {resp.status}")
                print(f"Upload response body: {result[:500]}")

                if resp.status == 200:
                    try:
                        result_json = json.loads(result)
                        asset_id = result_json.get('assetId')
                        if asset_id:
                            return asset_id
                        else:
                            raise Exception("Upload succeeded but no asset ID returned.")
                    except json.JSONDecodeError:
                        import re
                        match = re.search(r'assetId["\']?\s*[:=]\s*["\']?(\d+)', result)
                        if match:
                            return int(match.group(1))
                        raise Exception("Upload succeeded but could not parse response.")
                else:
                    try:
                        error_data = json.loads(result)
                        error_msg = error_data.get('errors', [{}])[0].get('message', 'Unknown error')
                        raise Exception(f"Upload failed: {error_msg}")
                    except:
                        raise Exception(f"Upload failed with status {resp.status}")
        except Exception as e:
            raise

    async def fetch_audio(self, asset_id: int, cookie: str = None):
        session = await self._get_session()
        url = f"https://assetdelivery.roblox.com/v1/assetId/{asset_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if cookie:
            headers['Cookie'] = f'.ROBLOSECURITY={cookie}'

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
                            raise Exception("Unexpected response from Roblox")
                    except json.JSONDecodeError:
                        pass

                if len(initial_data) < 1000:
                    try:
                        text = initial_data.decode('utf-8')
                        if '<html' in text.lower():
                            raise Exception("Roblox returned an error page – invalid asset?")
                        else:
                            raise Exception("Downloaded file is too small – not a valid audio file.")
                    except UnicodeDecodeError:
                        raise Exception("Downloaded file is not valid audio.")

                return initial_data

        except asyncio.TimeoutError:
            raise Exception("Request to Roblox timed out.")
        except Exception as e:
            raise

    def analyze_segment(self, audio: AudioSegment):
        duration = len(audio) / 1000.0
        sample_rate = audio.frame_rate
        sample_width = audio.sample_width
        bit_depth = sample_width * 8
        channels = audio.channels

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as tmp:
            audio.export(tmp.name, format="mp3")
            info = mediainfo(tmp.name)
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

        num_points = 400
        block_size = max(1, len(samples) // num_points)
        waveform = []
        for i in range(0, len(samples), block_size):
            block = samples[i:i+block_size]
            if block:
                rms_block = math.sqrt(sum(s*s for s in block) / len(block)) / max_val
                waveform.append(rms_block)

        return {
            "duration": duration,
            "sample_rate": sample_rate,
            "bit_depth": bit_depth,
            "channels": channels,
            "bitrate": bitrate,
            "dbfs": round(dbfs, 2) if dbfs != -float('inf') else "N/A",
            "lufs": round(lufs, 2) if lufs != -float('inf') else "N/A",
            "waveform": waveform,
            "max_val": max_val,
            "file_size": len(audio.raw_data)
        }

    async def analyze_audio(self, audio_data: bytes):
        if len(audio_data) > MAX_AUDIO_SIZE:
            raise Exception(f"Audio file too large: {len(audio_data)//1024//1024} MB (max {MAX_AUDIO_SIZE//1024//1024} MB)")

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            audio = AudioSegment.from_file(tmp_path)
            result = self.analyze_segment(audio)
            del audio
            gc.collect()
            return result
        except CouldntDecodeError:
            raise Exception("Invalid or unsupported audio file. The asset may not be a playable audio.")
        except Exception as e:
            raise Exception(f"Failed to process audio: {str(e)[:200]}")
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