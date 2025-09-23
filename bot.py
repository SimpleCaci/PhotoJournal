# bot.py
import os
import io
import zipfile
import random
import textwrap
from datetime import datetime, timedelta

import discord
from discord.ext import commands
import aiohttp
from PIL import Image, ImageDraw, ImageFont

from dotenv import load_dotenv

# =======================
# CONFIG
# =======================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Channels you want the bot to watch
CHANNEL_NAMES = ["daily-log", "notes", "documents", "projects", "memes", "recipes"]

# Files go here:
IMAGE_ROOT = "images"

# Prevent giant uploads (in MB)
MAX_IMAGE_SIZE_MB = 10

# Font (drop a handwriting .ttf here later if you want)
FONT_PATH = "arial.ttf"

# Text scale: smaller number -> larger text
CAPTION_SCALE = 30     # caption font size ~ image.width // CAPTION_SCALE
DATE_SCALE = 50        # date font size    ~ image.width // DATE_SCALE

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

os.makedirs(IMAGE_ROOT, exist_ok=True)

# =======================
# UTIL
# =======================
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def save_sidecar_caption(polaroid_path: str, caption: str, date_str: str):
    """
    Save a .txt file next to the polaroid with caption + date for search.
    """
    txt_path = polaroid_path + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        if caption:
            f.write(caption.strip() + "\n")
        f.write(date_str)

# =======================
# POLAROID MAKER
# =======================
def make_polaroid(input_path: str, output_path: str, caption: str = ""):
    """
    Polaroid style with:
      - Proportional borders
      - Caption at bottom
      - Digital clock-style date top-right, orange + semi-transparent
    """
    try:
        img = Image.open(input_path).convert("RGB")

        # Dynamic font sizes based on image size
        cap_size = max(20, img.width // 30)
        date_size = max(18, img.width // 45)

        # Caption and date text
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        caption = (caption or "").strip()

        # Load fonts
        try:
            font_caption = ImageFont.truetype(FONT_PATH, cap_size)
        except:
            font_caption = ImageFont.load_default()

        # Digital clock font for date, fallback if missing
        try:
            font_date = ImageFont.truetype("DS-DIGI.TTF", date_size)  # place font in folder
        except:
            font_date = ImageFont.load_default()

        # Wrap caption for bottom area
        cpl = max(22, img.width // 25)
        wrapped_caption = "\n".join(textwrap.wrap(caption, width=cpl)) if caption else ""

        # Scaled borders based on image size
        border_side = int(img.width * 0.08)
        border_top = int(img.height * 0.08)
        border_bottom = int(img.height * 0.15)

        # Adjust bottom border if caption tall
        dummy = Image.new("RGB", (10, 10))
        ddraw = ImageDraw.Draw(dummy)
        if wrapped_caption:
            cap_bbox = ddraw.textbbox((0, 0), wrapped_caption, font=font_caption)
            cap_h = cap_bbox[3] - cap_bbox[1]
            border_bottom = max(border_bottom, cap_h + cap_size * 2)

        # Final canvas size
        new_w = img.width + border_side * 2
        new_h = img.height + border_top + border_bottom
        canvas = Image.new("RGB", (new_w, new_h), "white")
        canvas.paste(img, (border_side, border_top))

        # Convert to RGBA for transparency
        overlay = canvas.convert("RGBA")
        draw = ImageDraw.Draw(overlay)

        # Draw date in orange, semi-transparent
        date_len = ddraw.textlength(date_str, font=font_date)
        date_x = border_side + img.width - int(date_len) - 15
        date_y = border_top + 15

        # Create semi-transparent layer
        date_layer = Image.new("RGBA", overlay.size, (255, 255, 255, 0))
        date_draw = ImageDraw.Draw(date_layer)
        date_draw.text((date_x, date_y), date_str, font=font_date, fill=(255, 165, 0, 180))  # orange w/ alpha
        overlay = Image.alpha_composite(overlay, date_layer)

        # Caption at bottom center
        if wrapped_caption:
            cap_bbox = ddraw.textbbox((0, 0), wrapped_caption, font=font_caption)
            cap_w = cap_bbox[2] - cap_bbox[0]
            cap_h = cap_bbox[3] - cap_bbox[1]
            cap_x = (new_w - cap_w) // 2
            cap_y = border_top + img.height + (border_bottom - cap_h) // 2

            # Shadow + main caption
            shadow_off = max(1, cap_size // 20)
            date_draw.text((cap_x + shadow_off, cap_y + shadow_off), wrapped_caption, font=font_caption, fill="gray")
            date_draw.text((cap_x, cap_y), wrapped_caption, font=font_caption, fill="black")
            overlay = Image.alpha_composite(overlay, date_layer)

        # Save final with transparency flattening
        final = overlay.convert("RGB")
        ensure_dir(os.path.dirname(output_path))
        final.save(output_path, quality=95)

        save_sidecar_caption(output_path, caption, date_str)

    except Exception as e:
        print(f"⚠️ Error converting {input_path}: {e}")

# =======================
# HELP
# =======================
@bot.command(name="helpme")
async def helpme(ctx):
    await ctx.send(
        "**Photo Bot Commands**\n"
        "`!list <channel>` – list polaroids in a channel\n"
        "`!send <channel> <filename>` – send a specific polaroid\n"
        "`!sendlist <channel> <file1> <file2> ...` – send multiple files\n"
        "`!sendday <channel> <YYYY-MM-DD>` – send all from a day\n"
        "`!senddaymulti <YYYY-MM-DD> <ch1> <ch2> ...` – send from many channels\n"
        "`!latest <channel>` – most recent polaroid\n"
        "`!random <channel>` – random polaroid\n"
        "`!caption <channel> <filename> <new caption>` – regenerate with caption\n"
        "`!archive <channel> <YYYY-MM-DD>` – zip + send that day’s polaroids\n"
        "`!search <channel> <keyword>` – find by caption text\n"
        "`!cleanupdays <N>` – delete files older than N days"
    )

# =======================
# EVENTS
# =======================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    for guild in bot.guilds:
        for ch_name in CHANNEL_NAMES:
            ch = discord.utils.get(guild.text_channels, name=ch_name)
            if ch:
                try:
                    await ch.send(f"📸 Watching #{ch_name} for images…")
                except Exception:
                    pass
    print("All set!")

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # Only process watched channels + messages with attachments
    if message.channel.name in CHANNEL_NAMES and message.attachments:
        base = os.path.join(IMAGE_ROOT, message.channel.name)
        today = datetime.now().strftime("%Y-%m-%d")
        folder_original = os.path.join(base, "original", today)
        folder_polaroid = os.path.join(base, "polaroid", today)
        ensure_dir(folder_original)
        ensure_dir(folder_polaroid)

        for att in message.attachments:


            if att.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                fname = f"{ts}_{att.filename}"
                p_original = os.path.join(folder_original, fname)
                p_polaroid = os.path.join(folder_polaroid, fname)

                # download original
                async with aiohttp.ClientSession() as session:
                    async with session.get(att.url) as resp:
                        if resp.status == 200:
                            with open(p_original, "wb") as f:
                                f.write(await resp.read())

                # make polaroid + auto-send
                make_polaroid(p_original, p_polaroid, message.content.strip())
                try:
                    await message.channel.send(file=discord.File(p_polaroid))
                except Exception as e:
                    await message.channel.send(f"Saved `{fname}`, but failed to send image: {e}")

    await bot.process_commands(message)

# =======================
# COMMANDS (Polaroid-only views)
# =======================
@bot.command(name="list")
async def list_images(ctx, channel_name: str):
    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    if not os.path.exists(folder):
        await ctx.send(f"❌ No folder found for `{channel_name}`.")
        return

    files = []
    for root, _, fs in os.walk(folder):
        files.extend([os.path.relpath(os.path.join(root, f), folder)
                      for f in fs if f.lower().endswith((".png", ".jpg", ".jpeg"))])

    if not files:
        await ctx.send(f"📂 No polaroids in `{channel_name}`.")
        return

    preview = "\n".join(sorted(files)[-50:])  # show last 50 to keep output reasonable
    await ctx.send(f"📂 **Polaroids in `{channel_name}`**\n```\n{preview}\n```")

@bot.command(name="send")
async def send_image(ctx, channel_name: str, *, file_name: str):
    channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if not channel:
        await ctx.send(f"❌ Channel `{channel_name}` not found.")
        return

    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    path = os.path.join(folder, file_name)
    if not os.path.exists(path):
        await ctx.send(f"❌ `{file_name}` not found in `{channel_name}` polaroids.")
        return

    await channel.send(file=discord.File(path))
    await ctx.send(f"✅ Sent `{file_name}` to #{channel_name}")

@bot.command(name="sendlist")
async def send_image_list(ctx, channel_name: str, *file_names: str):
    channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)
    if not channel:
        await ctx.send(f"❌ Channel `{channel_name}` not found.")
        return

    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    sent = 0
    for fn in file_names:
        path = os.path.join(folder, fn)
        if os.path.exists(path):
            await channel.send(file=discord.File(path))
            sent += 1
    if sent:
        await ctx.send(f"✅ Sent {sent} file(s) to #{channel_name}")
    else:
        await ctx.send("❌ No valid files to send.")

@bot.command(name="sendday")
async def send_images_by_day(ctx, channel_name: str, date_str: str):
    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid", date_str)
    if not os.path.exists(folder):
        await ctx.send(f"❌ No images for `{date_str}` in `{channel_name}`.")
        return
    files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    if not files:
        await ctx.send(f"📂 None found for that day.")
        return
    for f in sorted(files):
        await ctx.send(file=discord.File(os.path.join(folder, f)))
    await ctx.send(f"✅ Sent {len(files)} image(s) from {date_str} in #{channel_name}")

@bot.command(name="senddaymulti")
async def send_day_multi(ctx, date_str: str, *channels):
    total = 0
    for ch in channels:
        folder = os.path.join(IMAGE_ROOT, ch, "polaroid", date_str)
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            for f in sorted(files):
                await ctx.send(file=discord.File(os.path.join(folder, f)))
                total += 1
    if total == 0:
        await ctx.send(f"❌ No images for `{date_str}` in the selected channels.")
    else:
        await ctx.send(f"✅ Sent {total} image(s) from {', '.join(channels)} on {date_str}")

@bot.command(name="latest")
async def send_latest(ctx, channel_name: str):
    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    files = []
    for root, _, fs in os.walk(folder):
        files.extend([os.path.join(root, f) for f in fs if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    if not files:
        await ctx.send(f"❌ No polaroids in `{channel_name}`.")
        return
    latest = max(files, key=os.path.getmtime)
    await ctx.send(file=discord.File(latest))

@bot.command(name="random")
async def send_random(ctx, channel_name: str):
    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    files = []
    for root, _, fs in os.walk(folder):
        files.extend([os.path.join(root, f) for f in fs if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    if not files:
        await ctx.send(f"❌ No polaroids in `{channel_name}`.")
        return
    await ctx.send(file=discord.File(random.choice(files)))

@bot.command(name="caption")
async def update_caption(ctx, channel_name: str, file_name: str, *, new_caption: str):
    """
    Regenerate a polaroid using the original image (any day subfolder),
    save over the existing polaroid, and update the sidecar .txt.
    """
    orig_root = os.path.join(IMAGE_ROOT, channel_name, "original")
    polaroid_root = os.path.join(IMAGE_ROOT, channel_name, "polaroid")

    # locate by walking date subfolders
    orig_path = None
    for root, _, fs in os.walk(orig_root):
        if file_name in fs:
            orig_path = os.path.join(root, file_name)
            break

    if not orig_path:
        await ctx.send(f"❌ `{file_name}` not found in `{channel_name}` originals.")
        return

    # Determine matching polaroid folder by date (same relative date folder)
    # Extract the date folder from original path (…/original/YYYY-MM-DD/filename)
    try:
        date_folder = orig_path.split(os.sep)[-2]
    except Exception:
        date_folder = ""

    target_folder = os.path.join(polaroid_root, date_folder) if date_folder else polaroid_root
    ensure_dir(target_folder)
    polaroid_path = os.path.join(target_folder, file_name)

    make_polaroid(orig_path, polaroid_path, new_caption)
    await ctx.send(f"✅ Caption updated for `{file_name}`")

@bot.command(name="archive")
async def archive_day(ctx, channel_name: str, date_str: str):
    folder = os.path.join(IMAGE_ROOT, channel_name, "polaroid", date_str)
    if not os.path.exists(folder):
        await ctx.send(f"❌ No images for `{date_str}` in `{channel_name}`.")
        return
    files = [f for f in os.listdir(folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    if not files:
        await ctx.send("📂 None found for that day.")
        return

    zip_name = f"{channel_name}_{date_str}.zip"
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(os.path.join(folder, f), arcname=f)
    await ctx.send(file=discord.File(zip_name))
    os.remove(zip_name)

@bot.command(name="search")
async def search_images(ctx, channel_name: str, *, keyword: str):
    """
    Search polaroid sidecar .txt files for a keyword and return matching images.
    """
    root = os.path.join(IMAGE_ROOT, channel_name, "polaroid")
    matches = []
    for r, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(".txt"):
                path = os.path.join(r, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        if keyword.lower() in fh.read().lower():
                            img_path = path[:-4]  # drop .txt
                            # ensure image exists
                            for ext in (".png", ".jpg", ".jpeg"):
                                if os.path.exists(img_path + ext):
                                    matches.append(img_path + ext)
                                    break
                except Exception:
                    pass

    if not matches:
        await ctx.send(f"❌ No matches for `{keyword}` in `{channel_name}`.")
        return

    # Send up to ~10 to avoid spam
    sent = 0
    for m in matches[:10]:
        await ctx.send(file=discord.File(m))
        sent += 1
    if len(matches) > 10:
        await ctx.send(f"…and {len(matches) - 10} more results not shown.")

@bot.command(name="cleanupdays")
async def cleanup_days(ctx, days: int):
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for root, _, fs in os.walk(IMAGE_ROOT):
        for f in fs:
            p = os.path.join(root, f)
            try:
                if datetime.fromtimestamp(os.path.getmtime(p)) < cutoff:
                    os.remove(p)
                    removed += 1
            except Exception:
                pass
    await ctx.send(f"🗑️ Removed {removed} file(s) older than {days} days.")

# =======================
# RUN
# =======================
bot.run(TOKEN)
