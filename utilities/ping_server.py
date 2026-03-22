import discord
import aiohttp
from discord import app_commands

from utilities.config import load_config, save_config

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

config = load_config()


def ensure_guild_config_defaults(guild_config: dict) -> dict:
    guild_config.setdefault("mention_type", "everyone")
    guild_config.setdefault("mention_id", None)
    guild_config.setdefault("excluded_channel_ids", [])
    return guild_config


def build_mention_text(guild_config: dict) -> str:
    mention_type = guild_config.get("mention_type", "everyone")

    if mention_type == "role":
        role_id = guild_config.get("mention_id")
        if role_id:
            return f"<@&{role_id}>"

    return "@everyone"


def build_allowed_mentions(guild_config: dict) -> dict:
    mention_type = guild_config.get("mention_type", "everyone")

    if mention_type == "role":
        role_id = guild_config.get("mention_id")
        if role_id:
            return {
                "parse": ["users"],
                "roles": [str(role_id)]
            }

    return {
        "parse": ["users", "everyone"]
    }


async def send_webhook_message(
    webhook_url: str,
    user_id: int,
    channel_mention: str,
    guild_config: dict
):
    target_mention = build_mention_text(guild_config)
    allowed_mentions = build_allowed_mentions(guild_config)

    payload = {
        "content": (
            f"<@{user_id}> just joined {channel_mention}. "
            f"Go say hi {target_mention}."
        ),
        "allowed_mentions": allowed_mentions
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload) as resp:
            if resp.status not in (200, 204):
                print(f"Webhook failed: {resp.status} | {await resp.text()}")


@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user}")


@client.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if before.channel == after.channel:
        return

    if after.channel is None:
        return

    guild_id = str(member.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        return

    guild_config = ensure_guild_config_defaults(guild_config)

    webhook_url = guild_config.get("webhook_url")
    if not webhook_url:
        return

    excluded_channel_ids = guild_config.get("excluded_channel_ids", [])
    if after.channel.id in excluded_channel_ids:
        return

    if len(after.channel.members) == 1:
        await send_webhook_message(
            webhook_url=webhook_url,
            user_id=member.id,
            channel_mention=after.channel.mention,
            guild_config=guild_config
        )


@tree.command(name="setup", description="Set the alert channel. Default ping target is @everyone.")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = str(interaction.guild.id)
    old_config = config.get(guild_id)

    if old_config:
        old_config = ensure_guild_config_defaults(old_config)

    if old_config and old_config.get("webhook_id"):
        try:
            old_webhook = await client.fetch_webhook(int(old_config["webhook_id"]))
            await old_webhook.delete(reason="Replacing PartyPing alert webhook")
        except Exception:
            pass

    webhook = await channel.create_webhook(name="PartyPing Alerts")

    excluded_channel_ids = []
    if old_config:
        excluded_channel_ids = old_config.get("excluded_channel_ids", [])

    config[guild_id] = {
        "webhook_url": webhook.url,
        "webhook_id": webhook.id,
        "channel_id": channel.id,
        "mention_type": "everyone",
        "mention_id": None,
        "excluded_channel_ids": excluded_channel_ids
    }
    save_config(config)

    await interaction.response.send_message(
        f"Done. Alerts will be sent to {channel.mention} and will ping @everyone.",
        ephemeral=True
    )


@tree.command(name="setrole", description="Set which role gets pinged. Leave empty to switch back to @everyone.")
@app_commands.checks.has_permissions(manage_guild=True)
async def setrole(interaction: discord.Interaction, role: discord.Role | None = None):
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        await interaction.response.send_message(
            "This server is not configured yet. Use `/setup #channel` first.",
            ephemeral=True
        )
        return

    guild_config = ensure_guild_config_defaults(guild_config)

    if role is None:
        guild_config["mention_type"] = "everyone"
        guild_config["mention_id"] = None
        config[guild_id] = guild_config
        save_config(config)

        await interaction.response.send_message(
            "Ping target reset to @everyone.",
            ephemeral=True
        )
        return

    guild_config["mention_type"] = "role"
    guild_config["mention_id"] = role.id
    config[guild_id] = guild_config
    save_config(config)

    await interaction.response.send_message(
        f"Ping target updated to {role.mention}.",
        ephemeral=True
    )


@tree.command(name="excludechannel", description="Exclude a voice channel from PartyPing alerts.")
@app_commands.checks.has_permissions(manage_guild=True)
async def excludechannel(interaction: discord.Interaction, channel: discord.VoiceChannel):
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        await interaction.response.send_message(
            "This server is not configured yet. Use `/setup #channel` first.",
            ephemeral=True
        )
        return

    guild_config = ensure_guild_config_defaults(guild_config)
    excluded_channel_ids = guild_config["excluded_channel_ids"]

    if channel.id in excluded_channel_ids:
        await interaction.response.send_message(
            f"{channel.mention} is already excluded.",
            ephemeral=True
        )
        return

    excluded_channel_ids.append(channel.id)
    config[guild_id] = guild_config
    save_config(config)

    await interaction.response.send_message(
        f"{channel.mention} will now be ignored by PartyPing.",
        ephemeral=True
    )


@tree.command(name="includechannel", description="Remove a voice channel from the excluded list.")
@app_commands.checks.has_permissions(manage_guild=True)
async def includechannel(interaction: discord.Interaction, channel: discord.VoiceChannel):
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        await interaction.response.send_message(
            "This server is not configured yet. Use `/setup #channel` first.",
            ephemeral=True
        )
        return

    guild_config = ensure_guild_config_defaults(guild_config)
    excluded_channel_ids = guild_config["excluded_channel_ids"]

    if channel.id not in excluded_channel_ids:
        await interaction.response.send_message(
            f"{channel.mention} is not currently excluded.",
            ephemeral=True
        )
        return

    excluded_channel_ids.remove(channel.id)
    config[guild_id] = guild_config
    save_config(config)

    await interaction.response.send_message(
        f"{channel.mention} will be included in PartyPing alerts again.",
        ephemeral=True
    )


@tree.command(name="status", description="Show the current alert channel setup.")
async def status(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        await interaction.response.send_message(
            "This server is not configured yet. Use `/setup #channel`.",
            ephemeral=True
        )
        return

    guild_config = ensure_guild_config_defaults(guild_config)

    channel_id = guild_config.get("channel_id")
    mention_type = guild_config.get("mention_type", "everyone")
    excluded_channel_ids = guild_config.get("excluded_channel_ids", [])

    if mention_type == "role" and guild_config.get("mention_id"):
        mention_text = f"<@&{guild_config['mention_id']}>"
    else:
        mention_text = "@everyone"

    if excluded_channel_ids:
        excluded_text = "\n".join(f"- <#{channel_id}>" for channel_id in excluded_channel_ids)
    else:
        excluded_text = "None"

    await interaction.response.send_message(
        f"Current alert channel: <#{channel_id}>\n"
        f"Current ping target: {mention_text}\n"
        f"Excluded voice channels:\n{excluded_text}",
        ephemeral=True
    )


@tree.command(name="disable", description="Disable alerts for this server without deleting the webhook.")
@app_commands.checks.has_permissions(manage_guild=True)
async def disable(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)

    if guild_id in config:
        del config[guild_id]
        save_config(config)

    await interaction.response.send_message(
        "PartyPing alerts disabled for this server.",
        ephemeral=True
    )


@tree.command(name="resetalerts", description="Remove all alert config for this server and delete the created webhook.")
@app_commands.checks.has_permissions(manage_guild=True)
async def resetalerts(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id)

    if not guild_config:
        await interaction.response.send_message(
            "This server has no alert setup to reset.",
            ephemeral=True
        )
        return

    deleted_webhook = False

    webhook_id = guild_config.get("webhook_id")
    if webhook_id:
        try:
            webhook = await client.fetch_webhook(int(webhook_id))
            await webhook.delete(reason="PartyPing alerts reset")
            deleted_webhook = True
        except Exception:
            deleted_webhook = False

    del config[guild_id]
    save_config(config)

    if deleted_webhook:
        await interaction.response.send_message(
            "All PartyPing alerts were reset and the created webhook was deleted.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "All PartyPing alerts were reset. I could not delete the webhook, probably because it was already gone or inaccessible.",
            ephemeral=True
        )


@setup.error
@setrole.error
@excludechannel.error
@includechannel.error
@disable.error
@resetalerts.error
async def admin_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        if interaction.response.is_done():
            await interaction.followup.send(
                "You need Manage Server permission to use this command.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You need Manage Server permission to use this command.",
                ephemeral=True
            )


def run_bot(bot_token: str):
    client.run(bot_token)