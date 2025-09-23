import discord
from discord.ext import commands
import os, aiohttp, textwrap, random, shutil
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
from dotenv import load_dotenv

# =======================
# CONFIG
# =======================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

CHANNEL_NAMES = ["daily-log", "notes", "documents", "projects", "memes", "recipes"]
IMAGE_ROOT = "images"
MAX_IMAGE_SIZE_MB = 10  # Prevent giant uploads
FONT_PATH = "arial.ttf"  # Change to handwriting font if you want

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

os.makedirs(IMAGE_ROOT, exist_ok=True)

# =======================
# POLAROID FUNCTION
# =======================
def make_polaroid(input_path, output_path, caption=""):
    try:
        image = Image.open(input_path).convert("RGB")

        # Auto text size scaling based on image width
        base_font_size = max(20, image.width // 30)  # bigger images → bigger text
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_text = f"{caption}\n{date_str}" if caption else date_str

        try:
            font = ImageFont.truetype(FONT_PATH, base_font_size)
        except:
            font = ImageFont.load_default()

        # Wrap text to avoid overflow
        max_chars = max(20, image.width // 25)
        wrapped_text = "\n".join(textwrap.wrap(full_text, width=max_chars))

        # Polaroid borders
        border_top = image.height // 20
        border_side = image.width // 20
        border_bottom_base = max(200, base_font_size * 4)  # adjust bottom space

        # Measure text size
        dummy_img = Image.new("RGB", (10, 10))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), wrapped_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        border_bottom = max(border_bottom_base, text_height + base_font_size * 3)

        # New image size
        new_width = max(image.width + border_side * 2, text_width + border_side * 2 + 40)
        new_height = image.height + border_top + border_bottom

        # Create background
        new_img = Image.new("RGB", (new_width, new_height), "white")
        new_img.paste(image, (border_side, border_top))

        # Draw text in the center of bottom area
        draw = ImageDraw.Draw(new_img)
        text_x = (new_width - text_width) // 2
        text_y = image.height + border_top + (border_bottom - text_height) // 2

        # Add slight shadow effect for fun
        shadow_offset = base_font_size // 15
        draw.text((text_x + shadow_offset, text_y + shadow_offset), wrapped_text, font=font, fill="gray")
        draw.text((text_x, text_y), wrapped_text, font=font, fill="black")

        # Save final image
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        new_img.save(output_path)
        print(f"📸 Polaroid saved with dynamic text: {output_path}")

    except Exception as e:
        print(f"⚠️ Error converting {input_path}: {e}")

# =======================
# HELP COMMAND
# =======================
@bot.command(name="helpme")
async def helpme(ctx):
    help_text = """
    **Photo Bot Commands**
    `!list <channel>` → List all Polaroids in a channel
    `!send <channel> <filename>` → Send a specific Polaroid
    `!sendlist <channel> <file1> <file2>` → Send multiple files
    `!sendday <channel> <YYYY-MM-DD>` → Send all from a day
    `!latest <channel>` → Send the most recent Polaroid
    `!random <channel>` → Send a random Polaroid
    `!caption <channel> <filename> <new caption>` → Update caption & regenerate Polaroid
    `!cleanupdays <N>` → Delete files older than N days
    """
    await ctx.send(help_text)

# =======================
# EVENTS
# =======================
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
        base_folder = os.path.join(IMAGE_ROOT, message.channel.name)
        today = datetime.now().strftime("%Y-%m-%d")
        original_folder = os.path.join(base_folder, "original", today)
        polaroid_folder = os.path.join(base_folder, "polaroid", today)
        os.makedirs(original_folder, exist_ok=True)
        os.makedirs(polaroid_folder, exist_ok=True)

        for attachment in message.attachments:
            if attachment.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                await message.channel.send(f"⚠️ `{attachment.filename}` is too large! Skipping...")
                continue

            if attachment.filename.lower().endswith(("png", "jpg", "jpeg", "gif", "webp")):
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = f"{timestamp}_{attachment.filename}"

                original_path = os.path.join(original_folder, filename)
                polaroid_path = os.path.join(polaroid_folder, filename)

                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            with open(original_path, "wb") as f:
                                f.write(await resp.read())

                make_polaroid(original_path, polaroid_path, message.content.strip())
                await message.channel.send(f"✅ `{filename}` saved as Polaroid!")

    await bot.process_commands(message)

# =======================
# NEW COMMANDS
# =======================
@bot.command(name="latest")
async def send_latest(ctx, channel_name: str):
    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    all_files = []
    for root, _, files in os.walk(folder):
        all_files.extend([os.path.join(root, f) for f in files if f.lower().endswith(("png","jpg","jpeg"))])
    if not all_files:
        await ctx.send(f"❌ No Polaroids in `{channel_name}`.")
        return
    latest_file = max(all_files, key=os.path.getmtime)
    await ctx.send(file=discord.File(latest_file))

@bot.command(name="random")
async def send_random(ctx, channel_name: str):
    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    all_files = []
    for root, _, files in os.walk(folder):
        all_files.extend([os.path.join(root, f) for f in files if f.lower().endswith(("png","jpg","jpeg"))])
    if not all_files:
        await ctx.send(f"❌ No Polaroids in `{channel_name}`.")
        return
    random_file = random.choice(all_files)
    await ctx.send(file=discord.File(random_file))

@bot.command(name="caption")
async def update_caption(ctx, channel_name: str, file_name: str, *, new_caption: str):
    polaroid_folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    original_folder = os.path.join(IMAGE_ROOT, channel_name, "original")
    for root, _, files in os.walk(original_folder):
        if file_name in files:
            original_path = os.path.join(root, file_name)
            polaroid_path = os.path.join(polaroid_folder, file_name)
            make_polaroid(original_path, polaroid_path, new_caption)
            await ctx.send(f"✅ Caption updated for `{file_name}`")
            return
    await ctx.send(f"❌ File `{file_name}` not found in `{channel_name}`.")

@bot.command(name="cleanupdays")
async def cleanup_days(ctx, days: int):
    cutoff = datetime.now() - timedelta(days=days)
    deleted_files = 0
    for root, _, files in os.walk(IMAGE_ROOT):
        for f in files:
            f_path = os.path.join(root, f)
            if datetime.fromtimestamp(os.path.getmtime(f_path)) < cutoff:
                os.remove(f_path)
                deleted_files += 1
    await ctx.send(f"🗑️ Deleted {deleted_files} files older than {days} days.")

# =======================
# RUN BOT
# =======================
bot.run(TOKEN)
