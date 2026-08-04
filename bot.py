import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import io
import re

from config import DISCORD_TOKEN
from audio_fetcher import RobloxAudioFetcher
from waveform import generate_waveform_image, waveform_to_bytes

# Bot setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
fetcher = RobloxAudioFetcher()

# Helper to extract asset ID from various formats
def extract_asset_id(input_str: str) -> int:
    """Extract Roblox asset ID from various formats."""
    # Check for direct numeric ID
    if input_str.isdigit():
        return int(input_str)
    
    # Check for rbxassetid://123456789
    match = re.search(r'rbxassetid://(\d+)', input_str)
    if match:
        return int(match.group(1))
    
    # Check for roblox.com/asset/?id=123456789
    match = re.search(r'roblox\.com/asset/\?id=(\d+)', input_str)
    if match:
        return int(match.group(1))
    
    # Check for marketplace URLs
    match = re.search(r'marketplace/asset/(\d+)', input_str)
    if match:
        return int(match.group(1))
    
    raise ValueError("Could not extract asset ID from input")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="audioinfo", description="Get detailed info about a Roblox audio asset")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audioinfo(interaction: discord.Interaction, asset: str):
    """Fetch and display audio information."""
    
    await interaction.response.defer()
    
    try:
        asset_id = extract_asset_id(asset)
    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
        return
    
    try:
        # Fetch audio data
        audio_data = await fetcher.fetch_audio(asset_id)
        
        if not audio_data or len(audio_data) < 100:
            await interaction.followup.send("❌ Failed to download audio (file too small or invalid)")
            return
        
        # Analyze audio
        info = await fetcher.analyze_audio(audio_data)
        
        # Generate waveform image
        waveform_img = generate_waveform_image(
            info["waveform"],
            width=600,
            height=150,
            color="#00FF88",
            bg_color="#1a1a2e"
        )
        img_bytes = waveform_to_bytes(waveform_img)
        file = discord.File(io.BytesIO(img_bytes), filename="waveform.png")
        
        # Build embed
        embed = discord.Embed(
            title=f"🎵 Roblox Audio Info",
            description=f"Asset ID: `{asset_id}`",
            color=0x00FF88
        )
        
        embed.add_field(
            name="⏱️ Duration",
            value=f"{info['duration']} seconds",
            inline=True
        )
        embed.add_field(
            name="🎛️ Sample Rate",
            value=f"{info['sample_rate']} Hz",
            inline=True
        )
        embed.add_field(
            name="📊 Bit Depth",
            value=f"{info['bit_depth']}-bit",
            inline=True
        )
        embed.add_field(
            name="🔊 Channels",
            value=f"{info['channels']}",
            inline=True
        )
        embed.add_field(
            name="📦 Bitrate",
            value=info['bitrate'],
            inline=True
        )
        embed.add_field(
            name="📈 dBFS",
            value=f"{info['dbfs']} dB",
            inline=True
        )
        embed.add_field(
            name="🔊 LUFS",
            value=f"{info['lufs']} LUFS",
            inline=True
        )
        
        embed.set_image(url="attachment://waveform.png")
        embed.set_footer(text="Data fetched from Roblox • Waveform visualization")
        
        await interaction.followup.send(embed=embed, file=file)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="audiowaveform", description="Generate a waveform image for a Roblox audio")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audiowaveform(interaction: discord.Interaction, asset: str):
    """Generate just the waveform image."""
    
    await interaction.response.defer()
    
    try:
        asset_id = extract_asset_id(asset)
    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
        return
    
    try:
        audio_data = await fetcher.fetch_audio(asset_id)
        info = await fetcher.analyze_audio(audio_data)
        
        waveform_img = generate_waveform_image(
            info["waveform"],
            width=800,
            height=200,
            color="#00FF88",
            bg_color="#1a1a2e"
        )
        img_bytes = waveform_to_bytes(waveform_img)
        file = discord.File(io.BytesIO(img_bytes), filename="waveform.png")
        
        embed = discord.Embed(
            title=f"📊 Waveform for Asset {asset_id}",
            color=0x00FF88
        )
        embed.set_image(url="attachment://waveform.png")
        embed.set_footer(text=f"Duration: {info['duration']}s • Sample Rate: {info['sample_rate']}Hz")
        
        await interaction.followup.send(embed=embed, file=file)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="audiostreaminfo", description="Get stream-level audio info (sample rate, bitrate, etc.)")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audiostreaminfo(interaction: discord.Interaction, asset: str):
    """Get detailed stream information."""
    
    await interaction.response.defer()
    
    try:
        asset_id = extract_asset_id(asset)
    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
        return
    
    try:
        audio_data = await fetcher.fetch_audio(asset_id)
        info = await fetcher.analyze_audio(audio_data)
        
        embed = discord.Embed(
            title=f"🎛️ Audio Stream Info",
            description=f"Asset ID: `{asset_id}`",
            color=0x00FF88
        )
        
        embed.add_field(
            name="Sample Rate",
            value=f"{info['sample_rate']} Hz",
            inline=True
        )
        embed.add_field(
            name="Bit Depth",
            value=f"{info['bit_depth']}-bit",
            inline=True
        )
        embed.add_field(
            name="Channels",
            value=f"{info['channels']}",
            inline=True
        )
        embed.add_field(
            name="Bitrate",
            value=info['bitrate'],
            inline=True
        )
        embed.add_field(
            name="Duration",
            value=f"{info['duration']}s",
            inline=True
        )
        embed.add_field(
            name="File Size",
            value=f"{len(audio_data) // 1024} KB",
            inline=True
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="audiodbfs", description="Get dBFS (decibels relative to full scale) of a Roblox audio")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audiodbfs(interaction: discord.Interaction, asset: str):
    """Get dBFS value."""
    
    await interaction.response.defer()
    
    try:
        asset_id = extract_asset_id(asset)
    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
        return
    
    try:
        audio_data = await fetcher.fetch_audio(asset_id)
        info = await fetcher.analyze_audio(audio_data)
        
        embed = discord.Embed(
            title=f"📈 dBFS for Asset {asset_id}",
            description=f"**{info['dbfs']} dB**",
            color=0x00FF88
        )
        embed.add_field(
            name="What is dBFS?",
            value="Decibels relative to full scale. 0 dBFS is the maximum possible digital level. Lower values mean quieter audio.",
            inline=False
        )
        embed.set_footer(text="Values closer to 0 = louder")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="audiolufs", description="Get LUFS (Loudness Units Full Scale) of a Roblox audio")
@app_commands.describe(asset="Roblox audio asset ID or URL")
async def audiolufs(interaction: discord.Interaction, asset: str):
    """Get LUFS value."""
    
    await interaction.response.defer()
    
    try:
        asset_id = extract_asset_id(asset)
    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
        return
    
    try:
        audio_data = await fetcher.fetch_audio(asset_id)
        info = await fetcher.analyze_audio(audio_data)
        
        embed = discord.Embed(
            title=f"🔊 LUFS for Asset {asset_id}",
            description=f"**{info['lufs']} LUFS**",
            color=0x00FF88
        )
        embed.add_field(
            name="What is LUFS?",
            value="Loudness Units Full Scale. A measure of perceived loudness. Typical values: -23 LUFS (broadcast), -14 LUFS (streaming).",
            inline=False
        )
        embed.set_footer(text="Higher values = perceived louder")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

async def main():
    async with fetcher:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())