import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import io
import re
import tempfile
import os
import json
from datetime import datetime
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from config import DISCORD_TOKEN, MAIN_COOKIE
from audio_fetcher import RobloxAudioFetcher
from waveform import generate_waveform_image, waveform_to_bytes

TRACKING_FILE = "tracking.json"
USER_COOKIES_FILE = "user_cookies.json"

if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN not set.")

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)
fetcher = RobloxAudioFetcher()

def load_tracking():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'r') as f:
            return json.load(f)
    return {"assets": {}}

def save_tracking(data):
    with open(TRACKING_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_user_cookies():
    if os.path.exists(USER_COOKIES_FILE):
        with open(USER_COOKIES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_cookies(data):
    with open(USER_COOKIES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

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
    details = await fetcher.fetch_asset_details(asset_id, MAIN_COOKIE)
    audio_data = await fetcher.fetch_audio(asset_id, MAIN_COOKIE)
    if not audio_data or len(audio_data) < 1000:
        raise Exception("Downloaded file is too small – not a valid audio asset.")

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name

    try:
        try:
            audio = AudioSegment.from_file(tmp_path)
        except CouldntDecodeError:
            raise Exception("Invalid or unsupported audio file. The asset may not be a playable audio.")
        except Exception as e:
            raise Exception(f"Failed to process audio: {str(e)[:100]}")

        info = fetcher.analyze_segment(audio)
        info["file_size"] = len(audio_data)

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
    bot.loop.create_task(check_moderation_status())

async def check_moderation_status():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            tracking_data = load_tracking()
            assets = tracking_data.get("assets", {})
            for asset_id_str, user_id in assets.items():
                asset_id = int(asset_id_str)
                status = await fetcher.fetch_asset_moderation_status(asset_id, MAIN_COOKIE)
                if status.get("moderated", False):
                    user = await bot.fetch_user(user_id)
                    if user:
                        try:
                            await user.send(f"Asset {asset_id} has been moderated or deleted.")
                        except:
                            pass
                    tracking_data["assets"][asset_id_str] = {"moderated": True, "user_id": user_id}
                else:
                    tracking_data["assets"][asset_id_str] = {"moderated": False, "user_id": user_id}
            save_tracking(tracking_data)
        except Exception:
            pass
        await asyncio.sleep(86400)

@bot.tree.command(name="help", description="Show all available commands and how to use them")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Help - Available Commands",
        color=0x00FF88
    )
    embed.add_field(
        name="/audioinfo <asset>",
        value="Get detailed info about a Roblox audio asset (duration, sample rate, bitrate, waveform, etc.)",
        inline=False
    )
    embed.add_field(
        name="/track <add|remove|list> [asset]",
        value="Track assets for moderation changes. You'll be DM'd if an asset gets moderated.",
        inline=False
    )
    embed.add_field(
        name="/cookieset <cookie>",
        value="Store your personal .ROBLOSECURITY cookie for uploads.",
        inline=False
    )
    embed.add_field(
        name="/cookieremove",
        value="Remove your stored cookie.",
        inline=False
    )
    embed.add_field(
        name="/cookieshow",
        value="Check if you have a cookie stored.",
        inline=False
    )
    embed.add_field(
        name="/checkcookie",
        value="Check if your stored cookie is valid.",
        inline=False
    )
    embed.add_field(
        name="/upload (with attachment)",
        value="Upload an audio file to Roblox (group 11425892). You must set a cookie first.",
        inline=False
    )
    embed.add_field(
        name="Examples",
        value=(
            "`/audioinfo 1845655576`\n"
            "`/track add 123456`\n"
            "`/cookieset _|WARNING...`\n"
            "`/upload` (with attachment)"
        ),
        inline=False
    )
    embed.set_footer(text="Use /help anytime.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cookieset", description="Store your personal .ROBLOSECURITY cookie for uploads")
@app_commands.describe(cookie="The .ROBLOSECURITY cookie value")
async def cookieset(interaction: discord.Interaction, cookie: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    cookies = load_user_cookies()

    if not cookie:
        await interaction.followup.send("Please provide a cookie value.")
        return
    if not cookie.startswith("_|WARNING"):
        await interaction.followup.send("The cookie doesn't look like a valid .ROBLOSECURITY cookie.")
        return

    valid, msg = await fetcher._validate_cookie(cookie)
    if not valid:
        await interaction.followup.send(f"Cookie validation failed: {msg}")
        return

    cookies[user_id] = cookie
    save_user_cookies(cookies)
    await interaction.followup.send("Your cookie has been stored successfully! You can now use /upload with your own cookie.")

@bot.tree.command(name="cookieremove", description="Remove your stored cookie")
async def cookieremove(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    cookies = load_user_cookies()
    if user_id not in cookies:
        await interaction.followup.send("You don't have a cookie stored.")
        return
    del cookies[user_id]
    save_user_cookies(cookies)
    await interaction.followup.send("Your cookie has been removed.")

@bot.tree.command(name="cookieshow", description="Check if you have a cookie stored")
async def cookieshow(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    cookies = load_user_cookies()
    if user_id in cookies:
        await interaction.followup.send("You have a cookie stored for uploads.")
    else:
        await interaction.followup.send("You don't have a cookie stored. Use `/cookieset` to add one.")

@bot.tree.command(name="checkcookie", description="Check if your stored upload cookie is valid")
async def checkcookie(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    cookies = load_user_cookies()
    cookie = cookies.get(user_id)

    if not cookie:
        await interaction.followup.send("No personal cookie found. Use `/cookieset` to add one.")
        return

    valid, msg = await fetcher._validate_cookie(cookie)
    if valid:
        await interaction.followup.send("Your cookie is valid!")
    else:
        await interaction.followup.send(f"Your cookie is invalid: {msg}")

@bot.tree.command(name="track", description="Track a Roblox audio asset for moderation changes")
@app_commands.describe(action="add, remove, or list", asset="Asset ID or URL (for add/remove)")
async def track(interaction: discord.Interaction, action: str, asset: str = None):
    await interaction.response.defer()
    tracking_data = load_tracking()
    assets = tracking_data.get("assets", {})

    if action.lower() == "add":
        if not asset:
            await interaction.followup.send("Please provide an asset ID or URL to track.")
            return
        try:
            asset_id = extract_asset_id(asset)
        except ValueError as e:
            await interaction.followup.send(f"Error: {str(e)}")
            return

        if str(asset_id) in assets:
            await interaction.followup.send(f"Asset {asset_id} is already being tracked.")
            return

        assets[str(asset_id)] = {"user_id": interaction.user.id, "moderated": False}
        tracking_data["assets"] = assets
        save_tracking(tracking_data)
        await interaction.followup.send(f"Now tracking asset {asset_id}. You will be notified if it gets moderated.")

    elif action.lower() == "remove":
        if not asset:
            await interaction.followup.send("Please provide an asset ID or URL to remove from tracking.")
            return
        try:
            asset_id = extract_asset_id(asset)
        except ValueError as e:
            await interaction.followup.send(f"Error: {str(e)}")
            return

        if str(asset_id) not in assets:
            await interaction.followup.send(f"Asset {asset_id} is not being tracked.")
            return

        del assets[str(asset_id)]
        tracking_data["assets"] = assets
        save_tracking(tracking_data)
        await interaction.followup.send(f"Removed asset {asset_id} from tracking.")

    elif action.lower() == "list":
        if not assets:
            await interaction.followup.send("You are not tracking any assets.")
            return
        asset_list = "\n".join([f"- {aid}" for aid in assets.keys()])
        await interaction.followup.send(f"Tracked assets:\n{asset_list}")

    else:
        await interaction.followup.send("Invalid action. Use add, remove, or list.")

@bot.tree.command(name="upload", description="Upload an audio file to Roblox (uploads to group 11425892)")
@app_commands.describe(file="The audio file to upload")
async def upload(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer()

    user_id = str(interaction.user.id)
    cookies = load_user_cookies()
    cookie = cookies.get(user_id)

    if not cookie:
        await interaction.followup.send("No upload cookie found. Use `/cookieset` to add your .ROBLOSECURITY.")
        return

    valid, msg = await fetcher._validate_cookie(cookie)
    if not valid:
        await interaction.followup.send(f"Upload cookie invalid: {msg}\nUse `/cookieset` to update your cookie.")
        return

    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a')):
        await interaction.followup.send("Unsupported file format. Please upload MP3, WAV, OGG, FLAC, or M4A.")
        return

    try:
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            await interaction.followup.send("File too large. Maximum size is 10 MB.")
            return

        audio = AudioSegment.from_file(io.BytesIO(file_bytes), format=file.filename.split('.')[-1])

        MAX_DURATION_SEC = 419
        if len(audio) > MAX_DURATION_SEC * 1000:
            audio = audio[:MAX_DURATION_SEC * 1000]
            await interaction.followup.send(f"Audio trimmed to {MAX_DURATION_SEC//60}:{MAX_DURATION_SEC%60:02d} (max 7 minutes).")

        ogg_bytes = io.BytesIO()
        audio.export(ogg_bytes, format="ogg", parameters=["-q:a", "0"])
        ogg_bytes.seek(0)

        asset_id = await fetcher.upload_audio(
            ogg_bytes.read(),
            "audio.ogg",
            name="Audio",
            description="Audio",
            group_id=11425892,
            cookie=cookie
        )

        tracking_data = load_tracking()
        assets = tracking_data.get("assets", {})
        assets[str(asset_id)] = {"user_id": interaction.user.id, "moderated": False}
        tracking_data["assets"] = assets
        save_tracking(tracking_data)

        await interaction.followup.send(f"Upload successful! Asset ID: {asset_id}\nYou will be notified if it gets moderated.")

    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 1900:
            error_msg = error_msg[:1900] + "…"
        await interaction.followup.send(f"Upload failed: {error_msg}")

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

async def send_audio_info(destination, asset_id: int, details: dict, info: dict, ogg_path: str = None):
    duration_str = format_duration(info["duration"])
    size_mb = info["file_size"] / (1024 * 1024)
    size_str = f"{size_mb:.2f} MB"

    creator_name = details.get("name", "Unknown") if details else "Unknown"
    artist_name = creator_name

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