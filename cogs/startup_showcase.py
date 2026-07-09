# cogs/startup_showcase.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import datetime

# ─────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────
SHOWCASE_CHANNEL_ID = 1524586288127283290
DB_FILEPATH = "startups_showcase.json"
PRIMARY_FOUNDER_ID = 759445506426142781


# ─────────────────────────────────────────────────
# Database Helpers
# ─────────────────────────────────────────────────
def load_db() -> dict:
    if not os.path.exists(DB_FILEPATH):
        data = {"next_id": 1, "showcases": {}}
        with open(DB_FILEPATH, "w") as f:
            json.dump(data, f, indent=4)
        return data
    with open(DB_FILEPATH, "r") as f:
        return json.load(f)


def save_db(db: dict):
    with open(DB_FILEPATH, "w") as f:
        json.dump(db, f, indent=4)


def get_showcase_by_message_id(db: dict, message_id: int) -> dict | None:
    for s in db.get("showcases", {}).values():
        if s.get("message_id") == message_id:
            return s
    return None


# ─────────────────────────────────────────────────
# Persistent View for Showcase Card Buttons
# ─────────────────────────────────────────────────
class ShowcaseVoteView(discord.ui.View):
    def __init__(self, website_url: str | None = None):
        super().__init__(timeout=None)
        if website_url and website_url.startswith(("http://", "https://")):
            self.add_item(
                discord.ui.Button(
                    label="🌐 Visit Website",
                    url=website_url,
                    style=discord.ButtonStyle.link
                )
            )

    @discord.ui.button(
        label="🚀 Upvote",
        style=discord.ButtonStyle.primary,
        custom_id="showcase_upvote_button"
    )
    async def upvote_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = load_db()
        showcase = get_showcase_by_message_id(db, interaction.message.id)
        if not showcase:
            return await interaction.response.send_message(
                "❌ Could not find showcase data in database.", ephemeral=True
            )

        upvotes: list[int] = showcase.setdefault("upvotes", [])
        user_id = interaction.user.id

        if user_id in upvotes:
            upvotes.remove(user_id)
            msg = f"↩️ Removed your upvote from **{showcase['name']}**."
        else:
            upvotes.append(user_id)
            msg = f"🚀 You upvoted **{showcase['name']}**! Total Upvotes: **{len(upvotes)}**"

        save_db(db)

        # Update button label live
        button.label = f"🚀 Upvote ({len(upvotes)})"
        try:
            await interaction.message.edit(view=self)
        except Exception as e:
            print(f"[StartupShowcase] Failed to edit view button label: {e}")

        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(
        label="💬 Discussion Thread",
        style=discord.ButtonStyle.secondary,
        custom_id="showcase_discuss_button"
    )
    async def discuss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = load_db()
        showcase = get_showcase_by_message_id(db, interaction.message.id)
        if not showcase:
            return await interaction.response.send_message(
                "❌ Could not find showcase data in database.", ephemeral=True
            )

        thread_id = showcase.get("thread_id")
        if thread_id:
            thread = interaction.guild.get_thread(thread_id)
            if not thread:
                try:
                    thread = await interaction.guild.fetch_channel(thread_id)
                except Exception:
                    thread = None
            if thread:
                return await interaction.response.send_message(
                    f"💬 Discussion thread is already open here: {thread.mention}",
                    ephemeral=True
                )

        # Create new thread attached to the showcase post
        try:
            thread = await interaction.message.create_thread(
                name=f"💬 {showcase['name']} — Q&A & Discussion",
                auto_archive_duration=10080
            )
            showcase["thread_id"] = thread.id
            save_db(db)

            founder_id = showcase["founder_id"]
            founder_mention = f"<@{founder_id}>"
            await thread.send(
                f"👋 Welcome to the discussion thread for **{showcase['name']}**!\n"
                f"Founder: {founder_mention}\n\n"
                f"Feel free to ask questions, share feedback, or explore collaboration opportunities here."
            )
            await interaction.response.send_message(
                f"✅ Discussion thread created: {thread.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Missing permissions to create threads in this channel.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error creating discussion thread: {e}",
                ephemeral=True
            )


# ─────────────────────────────────────────────────
# Interactive Modal for Launch Submission
# ─────────────────────────────────────────────────
class ShowcaseLaunchModal(discord.ui.Modal, title="🚀 Launch Startup Showcase"):
    startup_name = discord.ui.TextInput(
        label="Startup Name",
        placeholder="e.g. Chaldal, Pathao, Shikho",
        max_length=50,
        required=True
    )
    tagline = discord.ui.TextInput(
        label="One-Liner Tagline",
        placeholder="e.g. Online grocery delivery platform in Bangladesh",
        max_length=100,
        required=True
    )
    category = discord.ui.TextInput(
        label="Category / Sector",
        placeholder="e.g. FinTech, EdTech, E-Commerce, SaaS, AI/ML",
        max_length=40,
        required=True
    )
    link = discord.ui.TextInput(
        label="Website / App URL",
        placeholder="https://yourstartup.com",
        max_length=150,
        required=True
    )
    pitch = discord.ui.TextInput(
        label="Pitch / Problem & Solution",
        style=discord.TextStyle.paragraph,
        placeholder="Describe what problem you solve, how your product works, and any current traction...",
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Ensure URL formatting
        url = self.link.value.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        channel = interaction.guild.get_channel(SHOWCASE_CHANNEL_ID)
        if not channel:
            try:
                channel = await interaction.guild.fetch_channel(SHOWCASE_CHANNEL_ID)
            except Exception:
                return await interaction.response.send_message(
                    f"❌ Showcase channel (<#{SHOWCASE_CHANNEL_ID}>) not found or bot lacks access.",
                    ephemeral=True
                )

        db = load_db()
        showcase_id = db["next_id"]
        db["next_id"] += 1

        embed = discord.Embed(
            title=f"🚀 {self.startup_name.value} — {self.tagline.value}",
            description=self.pitch.value,
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="🏷️ Category", value=f"`{self.category.value}`", inline=True)
        embed.add_field(name="👑 Founder", value=interaction.user.mention, inline=True)
        embed.add_field(name="🌐 Website", value=f"[Visit Product]({url})", inline=True)
        embed.set_footer(
            text=f"Showcase ID: #{showcase_id} • Click 🚀 Upvote below to support!",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )

        view = ShowcaseVoteView(website_url=url)
        # Initialize button label
        view.children[0].label = "🚀 Upvote (0)"

        try:
            msg = await channel.send(embed=embed, view=view)
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"❌ Bot does not have permission to post messages in {channel.mention}.",
                ephemeral=True
            )

        db["showcases"][str(showcase_id)] = {
            "id": showcase_id,
            "founder_id": interaction.user.id,
            "name": self.startup_name.value,
            "tagline": self.tagline.value,
            "category": self.category.value,
            "link": url,
            "description": self.pitch.value,
            "message_id": msg.id,
            "channel_id": channel.id,
            "thread_id": None,
            "upvotes": [],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        save_db(db)

        await interaction.response.send_message(
            f"🎉 Congratulations! **{self.startup_name.value}** has been launched in {channel.mention}!\n"
            f"Community members can now upvote and discuss your startup.",
            ephemeral=True
        )


# ─────────────────────────────────────────────────
# Main Cog
# ─────────────────────────────────────────────────
class StartupShowcase(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client

    showcase_group = app_commands.Group(
        name="showcase",
        description="Launch, view, and manage startup showcases."
    )

    @showcase_group.command(name="launch", description="Submit and launch your startup on the Showcase Board.")
    async def showcase_launch(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ShowcaseLaunchModal())

    @showcase_group.command(name="leaderboard", description="View the top startups ranked by community upvotes.")
    async def showcase_leaderboard(self, interaction: discord.Interaction):
        db = load_db()
        showcases = list(db.get("showcases", {}).values())
        if not showcases:
            return await interaction.response.send_message(
                "ℹ️ No startups have been launched yet. Run `/showcase launch` to be the first!",
                ephemeral=True
            )

        # Sort by upvote count descending
        showcases.sort(key=lambda s: len(s.get("upvotes", [])), reverse=True)
        top_startups = showcases[:10]

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for index, s in enumerate(top_startups):
            rank_icon = medals[index] if index < 3 else f"`#{index + 1}`"
            upvote_count = len(s.get("upvotes", []))
            lines.append(
                f"{rank_icon} **{s['name']}** (`{s['category']}`) — **{upvote_count}** 🚀\n"
                f"└ *{s['tagline']}* • Founder: <@{s['founder_id']}>"
            )

        embed = discord.Embed(
            title="🏆 Startup Showcase Leaderboard",
            description="\n\n".join(lines),
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Total Showcases: {len(showcases)}")
        await interaction.response.send_message(embed=embed)

    @showcase_group.command(name="list", description="List all startup showcases launched by a user.")
    @app_commands.describe(user="Filter by a specific founder (leave blank for your own).")
    async def showcase_list(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        db = load_db()
        user_showcases = [
            s for s in db.get("showcases", {}).values() if s.get("founder_id") == target.id
        ]

        if not user_showcases:
            return await interaction.response.send_message(
                f"ℹ️ {target.mention} has not launched any startups yet.",
                ephemeral=True
            )

        lines = []
        for s in user_showcases:
            upvotes = len(s.get("upvotes", []))
            lines.append(
                f"• **#{s['id']} | {s['name']}** — {upvotes} 🚀 upvotes (`{s['category']}`)"
            )

        embed = discord.Embed(
            title=f"🚀 Startups Launched by {target.display_name}",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @showcase_group.command(name="delete", description="Delete a startup showcase post.")
    @app_commands.describe(showcase_id="The numeric ID of the showcase to delete.")
    async def showcase_delete(self, interaction: discord.Interaction, showcase_id: int):
        db = load_db()
        s = db["showcases"].get(str(showcase_id))
        if not s:
            return await interaction.response.send_message(
                f"❌ Showcase `#{showcase_id}` not found.",
                ephemeral=True
            )

        # Only the founder, server admin, or primary founder can delete
        is_founder = interaction.user.id == s["founder_id"]
        is_admin = interaction.user.guild_permissions.administrator
        is_primary_founder = interaction.user.id == PRIMARY_FOUNDER_ID

        if not (is_founder or is_admin or is_primary_founder):
            return await interaction.response.send_message(
                "❌ You do not have permission to delete this showcase post.",
                ephemeral=True
            )

        channel_id = s.get("channel_id", SHOWCASE_CHANNEL_ID)
        message_id = s.get("message_id")
        channel = interaction.guild.get_channel(channel_id)
        if channel and message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.delete()
            except Exception:
                pass

        db["showcases"].pop(str(showcase_id), None)
        save_db(db)

        await interaction.response.send_message(
            f"✅ Showcase `#{showcase_id}` (**{s['name']}**) has been deleted.",
            ephemeral=True
        )


async def setup(client):
    await client.add_cog(StartupShowcase(client))
