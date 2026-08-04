import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import io
import re
import tempfile
import os
from datetime import datetime
from pydub import AudioSegment

from config import DISCORD_TOKEN
from audio_fetcher import RobloxAudioFetcher
from waveform import generate_waveform_image, waveform_to_bytes

if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN not set.")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
fetcher = RobloxAudioFetcher()

def extract_asset_id(input_str: str) -> int:
    if input_str.isdigit():
        return int(input_str)
    match = re.search(r'rbxassetid://(\d+)', input_str)
    if match:
        return int(match.group(1))
    match = re.search(r'roblox\.com/asset/\?id=(\d+)', input_str)
    if match:
        return int(match.group(1))
    match = re.search(r'marketplace/asset/(\d+)', input_str)
    if match:
        return int(match.group(1))
    raise ValueError("Could not extract asset ID from input")

def format_duration(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"

async def process_audio(asset_input: str):
    asset_id = extract_asset_id(asset_input)
    details = await fetcher.fetch_asset_details(asset_id)
    audio_data = await fetcher.fetch_audio(asset_id)
    if not audio_data or len(audio_data) < 1000:
        raise Exception("Downloaded file is too small")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        audio = AudioSegment.from_file(tmp_path)
        info = fetcher.analyze_segment(audio)
        info["file_size"] = len(audio_data)  # actual file size in bytes

        ogg_path = None
        if len(audio_data) < 20 * 1024 * 1024:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_tmp:
                ogg_path = ogg_tmp.name
                audio.export(ogg_path, format="ogg")
        else:
            ogg_path = None

        return asset_id, details, info, ogg_path, audio
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception:
        pass

@bot.tree.command(name="audioinfo", description="Get detailed info about a Roblox audio asset")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audioinfo_slash(interaction: discord.Interaction, asset: str):
    await interaction.response.defer()
    try:
        asset_id, details, info, ogg_path, audio = await asyncio.wait_for(process_audio(asset), timeout=25.0)
        await send_audio_info(interaction.followup, asset_id, details, info, ogg_path)
        if ogg_path and os.path.exists(ogg_path):
            os.unlink(ogg_path)
        del audio
    except asyncio.TimeoutError:
        await interaction.followup.send("Command timed out.")
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 1900:
            error_msg = error_msg[:1900] + "…"
        await interaction.followup.send(f"Error: {error_msg}")

@bot.command(name="audioinfo", aliases=["ai"])
async def audioinfo_prefix(ctx: commands.Context, *, asset: str):
    async with ctx.typing():
        try:
            asset_id, details, info, ogg_path, audio = await asyncio.wait_for(process_audio(asset), timeout=25.0)
            await send_audio_info(ctx, asset_id, details, info, ogg_path)
            if ogg_path and os.path.exists(ogg_path):
                os.unlink(ogg_path)
            del audio
        except asyncio.TimeoutError:
            await ctx.send("Command timed out.")
        except Exception as e:
            error_msg = str(e)
            if len(error_msg) > 1900:
                error_msg = error_msg[:1900] + "…"
            await ctx.send(f"Error: {error_msg}")

async def send_audio_info(destination, asset_id: int, details: dict, info: dict, ogg_path: str = None):
    duration_str = format_duration(info["duration"])
    size_mb = info["file_size"] / (1024 * 1024)
    size_str = f"{size_mb:.2f} MB"

    creator_name = details.get("name", "Unknown") if details else "Unknown"
    artist_name = creator_name  # Could be different if we had separate artist field

    upload_date = "Unknown"
    if details and details.get("created"):
        try:
            dt = datetime.fromisoformat(details["created"].replace("Z", "+00:00"))
            upload_date = dt.strftime("%b %d, %Y %I:%M %p")
        except:
            pass

    waveform_img = generate_waveform_image(
        info["waveform"],
        width=600,
        height=150,
        color="#00FF88",
        bg_color="#1a1a2e"
    )
    img_bytes = waveform_to_bytes(waveform_img)
    waveform_file = discord.File(img_bytes, filename="waveform.png")

    files = [waveform_file]
    if ogg_path and os.path.exists(ogg_path) and os.path.getsize(ogg_path) < 25 * 1024 * 1024:
        ogg_file = discord.File(ogg_path, filename="audio.ogg")
        files.append(ogg_file)

    embed = discord.Embed(color=0x00FF88)
    embed.add_field(name="Creator", value=creator_name, inline=True)
    embed.add_field(name="Artist", value=artist_name, inline=True)
    embed.add_field(name="Favorites", value=details.get("favorite_count", "N/A") if details else "N/A", inline=True)
    embed.add_field(name="Duration", value=duration_str, inline=True)
    embed.add_field(name="Size", value=size_str, inline=True)
    embed.add_field(name="Format", value="OGG 48kHz", inline=True)
    embed.add_field(name="Bitrate", value=info['bitrate'], inline=True)
    embed.add_field(name="Loudness", value=f"{info['lufs']} LUFS", inline=True)
    embed.add_field(name="Peak", value=f"{info['dbfs']} dBFS", inline=True)
    embed.add_field(name="Uploaded", value=upload_date, inline=True)
    embed.set_image(url="attachment://waveform.png")

    await destination.send(embed=embed, files=files)

async def main():
    async with fetcher:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())