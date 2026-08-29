import os
import sqlite3
import discord

from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


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
    # EMBED (rectangle layout)
    # =====================================================

    embed = discord.Embed(
        title="NEW VOUCH",
        description="\u200b",
        color=EMBED_COLOR
    )

    embed.set_author(
        name=interaction.user.display_name,
        icon_url=interaction.user.display_avatar.url
    )

    embed.set_thumbnail(
        url=interaction.user.display_avatar.url
    )

    embed.add_field(
        name="Product",
        value=produit,
        inline=True
    )

    embed.add_field(
        name="Rating",
        value=f"{stars}\n{rating} / 5",
        inline=True
    )

    embed.add_field(
        name="Avis",
        value=avis,
        inline=False
    )

    embed.set_footer(
        text=f"Vouch #{vouch_id:04d}  •  Thank you for your trust ❤️"
    )


    # =====================================================
    # SEND EMBED
    # =====================================================

    await interaction.response.defer(ephemeral=True)

    try:

        await channel.send(
            content=interaction.user.mention,
            embed=embed
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