import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import io
import re

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

async def process_audio(asset_input: str):
    asset_id = extract_asset_id(asset_input)
    audio_data = await fetcher.fetch_audio(asset_id)
    if not audio_data or len(audio_data) < 1000:
        raise Exception("Downloaded file is too small – not a valid audio asset.")
    info = await fetcher.analyze_audio(audio_data)
    return asset_id, info

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception:
        pass

# ========== SLASH COMMAND ==========
@bot.tree.command(name="audioinfo", description="Get detailed info about a Roblox audio asset")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audioinfo_slash(interaction: discord.Interaction, asset: str):
    await interaction.response.defer()
    try:
        asset_id, info = await asyncio.wait_for(process_audio(asset), timeout=25.0)
        await send_audio_info(interaction.followup, asset_id, info, is_slash=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("Command timed out – Roblox may be slow or the file is too large.")
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 1900:
            error_msg = error_msg[:1900] + "… (truncated)"
        await interaction.followup.send(f"Error: {error_msg}")

# ========== PREFIX COMMAND ==========
@bot.command(name="audioinfo", aliases=["ai"])
async def audioinfo_prefix(ctx: commands.Context, *, asset: str):
    async with ctx.typing():
        try:
            asset_id, info = await asyncio.wait_for(process_audio(asset), timeout=25.0)
            await send_audio_info(ctx, asset_id, info, is_slash=False)
        except asyncio.TimeoutError:
            await ctx.send("Command timed out – Roblox may be slow or the file is too large.")
        except Exception as e:
            error_msg = str(e)
            if len(error_msg) > 1900:
                error_msg = error_msg[:1900] + "… (truncated)"
            await ctx.send(f"Error: {error_msg}")

# ========== SHARED RESPONSE BUILDER ==========
async def send_audio_info(destination, asset_id: int, info: dict, is_slash: bool):
    duration_minutes = round(info["duration"] / 60, 1)

    waveform_img = generate_waveform_image(
        info["waveform"],
        width=600,
        height=150,
        color="#00FF88",
        bg_color="#1a1a2e"
    )
    img_bytes = waveform_to_bytes(waveform_img)
    file = discord.File(img_bytes, filename="waveform.png")

    embed = discord.Embed(
        title="Roblox Audio Info",
        description=f"Asset ID: `{asset_id}`",
        color=0x00FF88
    )
    embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
    embed.add_field(name="Sample Rate", value=f"{info['sample_rate']} Hz", inline=True)
    embed.add_field(name="Bit Depth", value=f"{info['bit_depth']}-bit", inline=True)
    embed.add_field(name="Channels", value=f"{info['channels']}", inline=True)
    embed.add_field(name="Bitrate", value=info['bitrate'], inline=True)
    embed.add_field(name="dBFS", value=f"{info['dbfs']} dB", inline=True)
    embed.add_field(name="LUFS", value=f"{info['lufs']} LUFS", inline=True)
    embed.set_image(url="attachment://waveform.png")
    embed.set_footer(text="Data fetched from Roblox")

    if is_slash:
        await destination.send(embed=embed, file=file)
    else:
        await destination.send(embed=embed, file=file)

async def main():
    async with fetcher:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())