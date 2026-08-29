import os
import io
import sqlite3
import threading
import asyncio
import urllib.request

import discord

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

VOUCH_CHANNEL_NAME = "⭐│vouch"

EMBED_COLOR = discord.Color.from_rgb(255, 0, 0)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("vouches.db")

cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS vouches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    product TEXT NOT NULL,
    rating INTEGER NOT NULL,
    review TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

db.commit()


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print("======================================")
    print(f"✅ Logged in as {bot.user}")
    print("======================================")

    try:
        synced = await bot.tree.sync()

        print(f"✅ {len(synced)} slash command(s) synchronized")

    except Exception as error:

        print(f"❌ Sync error: {error}")


# =========================================================
# CARD RENDERING (PILLOW)
# =========================================================

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

def _load_font(size, bold=True):
    candidates = FONT_PATHS if bold else [p for p in FONT_PATHS if "ttf" in p]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fetch_avatar(url):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return img
    except Exception:
        return None


def _round_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def build_vouch_card(user_name, user_avatar_url, product, stars, rating, review, vouch_id):
    W, H = 880, 540
    img = Image.new("RGB", (W, H), (10, 10, 13))
    d = ImageDraw.Draw(img)

    # background gradient (top red glow -> dark)
    for y in range(H):
        t = y / H
        r = int(40 + (10 - 40) * t)
        g = int(9 + (7 - 9) * t)
        b = int(14 + (10 - 14) * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))

    # red corner glows
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for cx, cy, rad, col in [
        (120, -40, 320, (255, 46, 77)),
        (W - 110, H + 40, 280, (220, 20, 45)),
    ]:
        gd.ellipse([cx - rad, cy - rad * 0.6, cx + rad, cy + rad * 0.6],
                   fill=col + (60,))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img.paste(glow, (0, 0), glow)

    d = ImageDraw.Draw(img)

    # outer border
    d.rounded_rectangle([14, 14, W - 14, H - 14], radius=26,
                        outline=(255, 46, 77), width=3)

    # top accent bar
    d.rectangle([40, 44, W - 40, 52], fill=(255, 46, 77))

    # title
    title_font = _load_font(46, bold=True)
    d.text((W // 2, 80), "★  NEW VOUCH", font=title_font, fill=(255, 255, 255),
           anchor="mm")

    # avatar
    avatar = _fetch_avatar(user_avatar_url)
    av_size = 118
    if avatar is not None:
        avatar = avatar.resize((av_size, av_size), Image.LANCZOS)
        mask = _round_mask((av_size, av_size), 34)
        img.paste(avatar, (48, 130), mask)
        d = ImageDraw.Draw(img)
    else:
        d.rounded_rectangle([48, 130, 48 + av_size, 130 + av_size], radius=34,
                            outline=(255, 46, 77), width=3)

    # author name
    name_font = _load_font(36, bold=True)
    d.text((48 + av_size + 26, 148), user_name, font=name_font, fill=(255, 255, 255))

    # product
    p_label = _load_font(18, bold=True)
    lw = d.textlength("PRODUCT", font=p_label)
    d.text((48 + av_size + 26, 190), "Product", font=_load_font(18, bold=True),
           fill=(160, 168, 185))
    prod_font = _load_font(28, bold=True)
    d.text((48 + av_size + 26, 218), product, font=prod_font, fill=(255, 46, 77))

    # --- right column: rating + vouch number ---
    stars_font = _load_font(34, bold=True)
    d.text((W - 60, 150), stars, font=stars_font, fill=(255, 200, 60), anchor="ra")
    note_font = _load_font(22, bold=True)
    d.text((W - 60, 196), f"{rating}/5", font=note_font, fill=(220, 224, 235), anchor="ra")

    # vouch number box
    num_box_x = W - 60 - 210
    d.rounded_rectangle([num_box_x - 34, 120, num_box_x + 34 + 210, 176], radius=16,
                        outline=(255, 46, 77), width=2)
    vouch_font = _load_font(22, bold=True)
    d.text((num_box_x + 110, 128), f"#{vouch_id:04d}", font=vouch_font,
           fill=(255, 255, 255), anchor="ma")

    # review box (bottom)
    ry = 300
    rd = ImageDraw.Draw(img)
    rd.rounded_rectangle([48, ry, W - 48, ry + 170], radius=20,
                         outline=(60, 60, 78), width=2, fill=(18, 19, 25))
    review_font = _load_font(24, bold=False)
    max_w = (W - 96) - 48
    lines = []
    for word in (review or "").split():
        test = " ".join(lines + [word]) if lines else word
        lw_test = rd.textlength(test, font=review_font)
        if lines and lw_test > max_w:
            lines.append(word)
        else:
            if lines:
                lines[-1] = test
            else:
                lines.append(word)
    if not lines:
        lines = ["..."]
    lines = lines[:5]
    ty = ry + 28
    for line in lines:
        rd.text((48 + 24, ty), line, font=review_font, fill=(225, 228, 238))
        ty += 30

    # footer
    foot_font = _load_font(17, bold=True)
    rd.text((48, H - 52), "EDITOR3 • THANK YOU FOR YOUR TRUST", font=foot_font,
            fill=(120, 126, 140))
    rd.text((W - 48, H - 52), f"Vouch #{vouch_id:04d}", font=foot_font,
            fill=(255, 46, 77), anchor="ra")

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out



# =========================================================
# /VOUCH
# =========================================================

@bot.tree.command(
    name="vouch",
    description="Leave a vouch"
)
@app_commands.describe(
    produit="Product you purchased",
    note="Your rating",
    avis="Your review"
)
@app_commands.choices(
    note=[
        app_commands.Choice(name="⭐ 1/5", value=1),
        app_commands.Choice(name="⭐⭐ 2/5", value=2),
        app_commands.Choice(name="⭐⭐⭐ 3/5", value=3),
        app_commands.Choice(name="⭐⭐⭐⭐ 4/5", value=4),
        app_commands.Choice(name="⭐⭐⭐⭐⭐ 5/5", value=5)
    ]
)
async def vouch(
    interaction: discord.Interaction,
    produit: str,
    note: app_commands.Choice[int],
    avis: str
):

    # =====================================================
    # SERVER CHECK
    # =====================================================

    if interaction.guild is None:

        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )

        return


    # =====================================================
    # CHANNEL CHECK
    # =====================================================

    channel = discord.utils.get(
        interaction.guild.text_channels,
        name=VOUCH_CHANNEL_NAME
    )

    if channel is None:

        await interaction.response.send_message(
            f"❌ The channel `{VOUCH_CHANNEL_NAME}` does not exist.",
            ephemeral=True
        )

        return


    # =====================================================
    # ONLY ALLOW IN VOUCH CHANNEL
    # =====================================================

    if interaction.channel.id != channel.id:

        await interaction.response.send_message(
            f"❌ You can only use `/vouch` in {VOUCH_CHANNEL_NAME}.",
            ephemeral=True
        )

        return


    # =====================================================
    # CHECK USER CAN SEND MESSAGES
    # =====================================================

    permissions = channel.permissions_for(interaction.user)

    if not permissions.view_channel:

        await interaction.response.send_message(
            "❌ You cannot access this channel.",
            ephemeral=True
        )

        return


    if not permissions.send_messages:

        await interaction.response.send_message(
            "❌ You need permission to send messages in this channel to leave a vouch.",
            ephemeral=True
        )

        return


    # =====================================================
    # CHECK BOT PERMISSIONS
    # =====================================================

    bot_member = interaction.guild.me

    if bot_member is None:

        await interaction.response.send_message(
            "❌ I couldn't check my permissions.",
            ephemeral=True
        )

        return


    bot_permissions = channel.permissions_for(bot_member)

    if not bot_permissions.send_messages:

        await interaction.response.send_message(
            "❌ I don't have permission to send messages in the vouch channel.",
            ephemeral=True
        )

        return


    if not bot_permissions.embed_links:

        await interaction.response.send_message(
            "❌ I need the `Embed Links` permission.",
            ephemeral=True
        )

        return


    # =====================================================
    # RATING
    # =====================================================

    rating = note.value

    stars = "⭐" * rating + "☆" * (5 - rating)


    # =====================================================
    # SAVE DATABASE
    # =====================================================

    cursor.execute(
        """
        INSERT INTO vouches
        (user_id, username, product, rating, review)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            interaction.user.id,
            str(interaction.user),
            produit,
            rating,
            avis
        )
    )

    db.commit()

    vouch_id = cursor.lastrowid


    # =====================================================
    # GENERATE CARD IMAGE
    # =====================================================

    avatar_url = interaction.user.display_avatar.url

    card_bytes = await asyncio.to_thread(
        build_vouch_card,
        interaction.user.display_name,
        avatar_url,
        produit,
        stars,
        rating,
        avis,
        vouch_id
    )

    file = discord.File(card_bytes, filename="vouch.png")


    # =====================================================
    # SEND CARD
    # =====================================================

    await interaction.response.defer(ephemeral=True)

    try:

        await channel.send(
            content=interaction.user.mention,
            file=file
        )

    except discord.Forbidden:

        await interaction.followup.send(
            "❌ I don't have permission to send messages here.",
            ephemeral=True
        )

        return

    except discord.HTTPException:

        await interaction.followup.send(
            "❌ Discord rejected the message. Please try again.",
            ephemeral=True
        )

        return


    # =====================================================
    # SUCCESS
    # =====================================================

    await interaction.followup.send(
        "✅ Your vouch has been successfully recorded!",
        ephemeral=True
    )


# =========================================================
# /VOUCHES
# =========================================================

@bot.tree.command(
    name="vouches",
    description="Display vouch statistics"
)
async def vouches(interaction: discord.Interaction):

    cursor.execute(
        "SELECT COUNT(*) FROM vouches"
    )

    total = cursor.fetchone()[0]


    cursor.execute(
        "SELECT AVG(rating) FROM vouches"
    )

    average = cursor.fetchone()[0]


    if average is None:

        average_text = "No reviews yet"

    else:

        average_text = f"{average:.2f}/5 ⭐"


    embed = discord.Embed(
        title="📊 VOUCH STATISTICS",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="💬 Total Vouches",
        value=f"`{total}`",
        inline=True
    )

    embed.add_field(
        name="⭐ Average Rating",
        value=average_text,
        inline=True
    )


    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /AVIS
# =========================================================

@bot.tree.command(
    name="avis",
    description="Display the latest vouches"
)
async def avis(interaction: discord.Interaction):

    cursor.execute("""
        SELECT id, username, product, rating, review
        FROM vouches
        ORDER BY id DESC
        LIMIT 5
    """)

    results = cursor.fetchall()


    if not results:

        await interaction.response.send_message(
            "❌ No vouches recorded yet.",
            ephemeral=True
        )

        return


    embed = discord.Embed(
        title="⭐ LATEST VOUCHES",
        color=EMBED_COLOR
    )


    for vouch_id, username, product, rating, review in results:

        stars = "⭐" * rating + "☆" * (5 - rating)

        embed.add_field(
            name=f"#{vouch_id:04d} • {product}",
            value=(
                f"{stars}\n"
                f"**{review}**\n"
                f"👤 {username}"
            ),
            inline=False
        )


    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /MES-VOUCHES
# =========================================================

@bot.tree.command(
    name="mes-vouches",
    description="Display your vouches"
)
async def mes_vouches(interaction: discord.Interaction):

    cursor.execute(
        """
        SELECT COUNT(*), AVG(rating)
        FROM vouches
        WHERE user_id = ?
        """,
        (interaction.user.id,)
    )

    total, average = cursor.fetchone()


    if average is None:

        average_text = "No reviews yet"

    else:

        average_text = f"{average:.2f}/5 ⭐"


    embed = discord.Embed(
        title=f"📊 Vouches from {interaction.user.display_name}",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="💬 Total Vouches",
        value=f"`{total}`",
        inline=True
    )

    embed.add_field(
        name="⭐ Average Rating",
        value=average_text,
        inline=True
    )


    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# RENDER KEEP-ALIVE (needed for Render to see a running port)
# =========================================================

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class RenderHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Zyro vouch bot is running")
    def log_message(self, *args):
        pass

def keep_alive():
    port = int(os.getenv("PORT", "10000"))
    print(f"✅ Heartbeat server on port {port}")
    HTTPServer(("0.0.0.0", port), RenderHandler).serve_forever()

threading.Thread(target=keep_alive, daemon=True).start()


# =========================================================
# START BOT
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "❌ DISCORD_TOKEN is missing from your .env file."
    )


bot.run(TOKEN)