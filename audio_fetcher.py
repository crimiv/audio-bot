import io
import aiohttp
import asyncio
from pydub import AudioSegment
from pydub.utils import mediainfo
import tempfile
import os

class RobloxAudioFetcher:
    def __init__(self):
        self.session = None

    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def fetch_audio(self, asset_id: int):
        """Download audio from Roblox by asset ID."""
        session = await self._get_session()
        url = f"https://assetdelivery.roblox.com/v1/assetId/{asset_id}"
        
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to fetch asset: HTTP {resp.status}")
            
            # Roblox returns the audio file directly
            audio_data = await resp.read()
            
        return audio_data

    async def analyze_audio(self, audio_data: bytes):
        """Analyze audio and return metadata."""
        # Write to temp file for pydub processing
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            # Load audio with pydub
            audio = AudioSegment.from_file(tmp_path)
            
            # Get duration in seconds
            duration = len(audio) / 1000.0
            
            # Get sample rate (frame rate)
            sample_rate = audio.frame_rate
            
            # Get sample width (bytes per sample) -> bit depth
            sample_width = audio.sample_width
            bit_depth = sample_width * 8
            
            # Get channels
            channels = audio.channels
            
            # Get bitrate using mediainfo
            info = mediainfo(tmp_path)
            bitrate = info.get("bit_rate", "N/A")
            
            # If bitrate is a string like "128000", convert to kbps
            if bitrate != "N/A" and isinstance(bitrate, str):
                try:
                    bitrate_kbps = int(bitrate) // 1000
                    bitrate = f"{bitrate_kbps} kbps"
                except ValueError:
                    pass
            
            # Calculate dBFS (decibels relative to full scale)
            # Get raw samples and compute RMS
            samples = audio.get_array_of_samples()
            import math
            # Convert to float and compute RMS
            if len(samples) > 0:
                # Normalize based on sample width
                max_val = 2 ** (bit_depth - 1)
                float_samples = [s / max_val for s in samples]
                rms = math.sqrt(sum(s**2 for s in float_samples) / len(float_samples))
                if rms > 0:
                    dbfs = 20 * math.log10(rms)
                else:
                    dbfs = -float('inf')
            else:
                dbfs = -float('inf')
            
            # Estimate LUFS (simplified - for accurate LUFS use external lib)
            # We'll use RMS as a proxy and approximate
            if rms > 0:
                lufs = 20 * math.log10(rms) - 0.691  # Rough approximation
            else:
                lufs = -float('inf')
            
            # Get waveform samples for visualization
            # Downsample to a reasonable number of points
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
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def close(self):
        if self.session:
            await self.session.close()