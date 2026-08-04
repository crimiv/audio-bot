import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import io
import re

from config import DISCORD_TOKEN
from audio_fetcher import RobloxAudioFetcher
from waveform import generate_waveform_image, waveform_to_bytes

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

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}", flush=True)
    try:
        synced = await bot.tree.sync()
        print(f"📋 Synced {len(synced)} command(s)", flush=True)
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}", flush=True)

@bot.tree.command(name="audioinfo", description="Get detailed info about a Roblox audio asset")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audioinfo(interaction: discord.Interaction, asset: str):
    # Log BEFORE defer – this ensures we see the command in logs
    print(f"🔄 /audioinfo called for asset: {asset}", flush=True)
    await interaction.response.defer()
    print(f"⏳ Deferred interaction", flush=True)

    try:
        asset_id = extract_asset_id(asset)
        print(f"🔍 Extracted asset ID: {asset_id}", flush=True)
    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
        return

    try:
        # Wrap the whole processing in a timeout to avoid indefinite hanging
        async def process():
            audio_data = await fetcher.fetch_audio(asset_id)
            if not audio_data or len(audio_data) < 1000:
                raise Exception("Downloaded file is too small – not a valid audio asset.")
            print("📊 Analyzing audio...", flush=True)
            info = await fetcher.analyze_audio(audio_data)
            print("📊 Analysis complete.", flush=True)
            return info, audio_data

        # 25 second timeout for the entire operation
        info, audio_data = await asyncio.wait_for(process(), timeout=25.0)

        print("🎨 Generating waveform image...", flush=True)
        waveform_img = generate_waveform_image(
            info["waveform"],
            width=600,
            height=150,
            color="#00FF88",
            bg_color="#1a1a2e"
        )
        img_bytes = waveform_to_bytes(waveform_img)
        file = discord.File(io.BytesIO(img_bytes), filename="waveform.png")
        print("🎨 Waveform generated.", flush=True)

        embed = discord.Embed(
            title="🎵 Roblox Audio Info",
            description=f"Asset ID: `{asset_id}`",
            color=0x00FF88
        )
        embed.add_field(name="⏱️ Duration", value=f"{info['duration']} seconds", inline=True)
        embed.add_field(name="🎛️ Sample Rate", value=f"{info['sample_rate']} Hz", inline=True)
        embed.add_field(name="📊 Bit Depth", value=f"{info['bit_depth']}-bit", inline=True)
        embed.add_field(name="🔊 Channels", value=f"{info['channels']}", inline=True)
        embed.add_field(name="📦 Bitrate", value=info['bitrate'], inline=True)
        embed.add_field(name="📈 dBFS", value=f"{info['dbfs']} dB", inline=True)
        embed.add_field(name="🔊 LUFS", value=f"{info['lufs']} LUFS", inline=True)
        embed.set_image(url="attachment://waveform.png")
        embed.set_footer(text="Data fetched from Roblox • Waveform visualization")

        await interaction.followup.send(embed=embed, file=file)
        print("✅ Command completed successfully.", flush=True)

    except asyncio.TimeoutError:
        print("❌ Command timed out after 25 seconds", flush=True)
        await interaction.followup.send("❌ Command timed out – Roblox may be slow or the file is too large.")
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 1900:
            error_msg = error_msg[:1900] + "… (truncated)"
        print(f"❌ Error in command: {error_msg}", flush=True)
        try:
            await interaction.followup.send(f"❌ Error: {error_msg}")
        except Exception as followup_err:
            print(f"⚠️ Could not send error message: {followup_err}", flush=True)

async def main():
    async with fetcher:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())