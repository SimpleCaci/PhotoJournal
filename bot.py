import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime
import aiohttp

# Load environment variables from .env file
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")  # Token from .env

# List of channels to monitor (add more as needed)
CHANNEL_NAMES = ["main", "random", "memes"]

# Setup bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Root folder for all images
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
    # Ignore bot's own messages
    if message.author == bot.user:
        return

    # Only watch selected channels
    if message.channel.name in CHANNEL_NAMES:
        # If the message has attachments (images)
        if message.attachments:
            channel_folder = os.path.join(IMAGE_ROOT, message.channel.name)
            os.makedirs(channel_folder, exist_ok=True)

            for attachment in message.attachments:
                if attachment.filename.lower().endswith(("png", "jpg", "jpeg", "gif", "webp")):
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"{timestamp}_{attachment.filename}"
                    filepath = os.path.join(channel_folder, filename)

                    # Download the image
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            if resp.status == 200:
                                with open(filepath, "wb") as f:
                                    f.write(await resp.read())

                    # Save caption if message has text
                    if message.content.strip():
                        caption_path = filepath + ".txt"
                        with open(caption_path, "w", encoding="utf-8") as f:
                            f.write(message.content)

                    print(f"Saved image: {filename} in {channel_folder}")
                    await message.channel.send(f"✅ Saved `{filename}` with caption!")

    await bot.process_commands(message)

bot.run(TOKEN)
