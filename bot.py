import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime
import aiohttp

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Channels to watch
CHANNEL_NAMES = ["daily-log", "notes", "documents", "projects"]

# Setup bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Root folder
IMAGE_ROOT = "images"
os.makedirs(IMAGE_ROOT, exist_ok=True)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    for guild in bot.guilds:
        for channel_name in CHANNEL_NAMES:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                await channel.send(f"📸 Bot is watching #{channel_name} for images!")
                print(f"Watching #{channel_name} in {guild.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.channel.name in CHANNEL_NAMES and message.attachments:
        channel_folder = os.path.join(IMAGE_ROOT, message.channel.name)
        os.makedirs(channel_folder, exist_ok=True)

        for attachment in message.attachments:
            if attachment.filename.lower().endswith(("png", "jpg", "jpeg", "gif", "webp")):
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"{timestamp}_{attachment.filename}"
                filepath = os.path.join(channel_folder, filename)

                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(filepath, "wb") as f:
                                f.write(await resp.read())

                if message.content.strip():
                    caption_path = filepath + ".txt"
                    with open(caption_path, "w", encoding="utf-8") as f:
                        f.write(message.content)

                print(f"Saved image: {filename} in {channel_folder}")
                await message.channel.send(f"✅ Saved `{filename}` with caption!")
    await bot.process_commands(message)

# -----------------------------
# COMMAND: List all images in a folder
# -----------------------------
@bot.command(name="list")
async def list_images(ctx, channel_name: str):
    folder_path = os.path.join(IMAGE_ROOT, channel_name)
    if not os.path.exists(folder_path):
        await ctx.send(f"❌ No folder found for `{channel_name}`.")
        return

    files = [f for f in os.listdir(folder_path) if f.lower().endswith(("png", "jpg", "jpeg", "gif", "webp"))]
    if not files:
        await ctx.send(f"📂 No images found in `{channel_name}`.")
        return

    file_list = "\n".join(files)
    await ctx.send(f"📂 **Images in `{channel_name}`:**\n```\n{file_list}\n```")

# -----------------------------
# COMMAND: Send specific image
# -----------------------------
@bot.command(name="send")
async def send_image(ctx, channel_name: str, *, file_name: str):
    channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if channel is None:
        await ctx.send(f"❌ Channel `{channel_name}` not found.")
        return

    file_path = os.path.join(IMAGE_ROOT, channel_name, file_name)
    if not os.path.exists(file_path):
        await ctx.send(f"❌ File `{file_name}` not found in `{channel_name}` folder.")
        return

    await channel.send(file=discord.File(file_path))
    await ctx.send(f"✅ Sent `{file_name}` to #{channel_name}")

# -----------------------------
# COMMAND: Send multiple images from list
# -----------------------------
@bot.command(name="sendlist")
async def send_image_list(ctx, channel_name: str, *file_names: str):
    channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if channel is None:
        await ctx.send(f"❌ Channel `{channel_name}` not found.")
        return

    folder_path = os.path.join(IMAGE_ROOT, channel_name)
    sent_files = []
    for file_name in file_names:
        file_path = os.path.join(folder_path, file_name)
        if os.path.exists(file_path):
            await channel.send(file=discord.File(file_path))
            sent_files.append(file_name)

    if sent_files:
        await ctx.send(f"✅ Sent {len(sent_files)} files to #{channel_name}")
    else:
        await ctx.send(f"❌ No valid files found to send.")

# -----------------------------
# COMMAND: Send all images from a specific day
# -----------------------------
@bot.command(name="sendday")
async def send_images_by_day(ctx, channel_name: str, date_str: str):
    """Send all images from a given day (format: YYYY-MM-DD)"""
    channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if channel is None:
        await ctx.send(f"❌ Channel `{channel_name}` not found.")
        return

    folder_path = os.path.join(IMAGE_ROOT, channel_name)
    if not os.path.exists(folder_path):
        await ctx.send(f"❌ No folder found for `{channel_name}`.")
        return

    files = [f for f in os.listdir(folder_path) if f.startswith(date_str) and f.lower().endswith(("png", "jpg", "jpeg", "gif", "webp"))]
    if not files:
        await ctx.send(f"📂 No images found in `{channel_name}` for {date_str}.")
        return

    for file_name in files:
        file_path = os.path.join(folder_path, file_name)
        await channel.send(file=discord.File(file_path))

    await ctx.send(f"✅ Sent {len(files)} images from {date_str} in #{channel_name}")

bot.run(TOKEN)
