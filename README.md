# PartyPing - A Voice Chat Join Notification Bot

A Discord bot that posts an alert in a **text channel** when someone **joins a voice channel and is the first person in that channel**. The message mentions the joiner and pings `@everyone` or a **role** you configure, so people can jump in for a voice “party.”

Alerts are sent through a **webhook** created in your chosen text channel, so mentions follow normal Discord rules without the bot needing broad permissions everywhere.

## Requirements

- **Python 3.10+**
- A [Discord application](https://discord.com/developers/applications) with a bot user and token

## Discord setup

1. Developer Portal → your application → **Bot** → copy the token into `.env` as `BOT_TOKEN`.
2. **Privileged Gateway Intents:** you do **not** need Message Content Intent. The bot enables `guilds` and `voice_states` so it can see voice joins.
3. **OAuth2** → **URL Generator:** scopes **bot** and **applications.commands**. Suggested bot permissions:
  - **Manage Webhooks** (required so `/setup` can create the **PartyPing Alerts** webhook in the text channel you choose)
  - **View Channels** so slash-command options (e.g. voice channels) and visibility match what you expect
  - **Send Messages** / **Use Slash Commands** as needed for your server  
   If you use channel-specific permission overwrites, the bot still needs **Manage Webhooks** (and **View Channel**) on the **text channel** used in `/setup`.
4. Open the invite URL and add the bot to your server.

## Install and run

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

Create `.env` in the project root:

```env
BOT_TOKEN=your_bot_token_here
```

From the **repository root** (so the `utilities` package resolves), start the bot:

```bash
python run_bot.py
```

Slash commands are registered with `tree.sync()` **globally**. They usually appear quickly in small servers, but Discord can take **up to about an hour** to propagate global commands everywhere—if `/setup` does not show up immediately, wait and retry.

## Configuration


| Source                  | What it stores                                                                                                                                                                                                        |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.env`                  | `BOT_TOKEN` only — never commit this.                                                                                                                                                                                 |
| `utilities/config.json` | Per-guild settings: webhook URL/ID, alert text channel ID, ping target (`@everyone` vs role), and **excluded voice channel IDs**. Contains webhook secrets; keep it local or add it to `.gitignore` for public repos. |


Re-running `**/setup`** deletes the previous PartyPing webhook (when the bot can still access it), creates a new one in the chosen text channel, resets the ping target to `@everyone`, and **keeps your voice-channel exclusion list**.

## Commands

Admin commands use Discord’s **Manage Server** permission (`manage_guild`); responses are **ephemeral**. `**/status`** has no admin check—any member can run it (still ephemeral).


| Command           | Description                                                                                                                                                                                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/setup`          | Choose a **text channel**. Creates the PartyPing webhook there and enables alerts for this server. Ping target defaults to `@everyone`.                                                                                                                                         |
| `/setrole`        | Pass a **role** to ping instead of `@everyone`, or run with no role to reset to `@everyone`.                                                                                                                                                                                    |
| `/excludechannel` | Pick a **voice channel** that should **never** trigger alerts (e.g. AFK or solo hangout rooms).                                                                                                                                                                                 |
| `/includechannel` | Remove a voice channel from the exclusion list.                                                                                                                                                                                                                                 |
| `/status`         | Shows alert text channel, current ping target, and all excluded voice channels.                                                                                                                                                                                                 |
| `/disable`        | Removes saved config for this server only. The **webhook may still exist** in Discord; `**/resetalerts` will not run** after this (there is no saved config). Delete the **PartyPing Alerts** webhook under the text channel’s **Integrations → Webhooks** if you want it gone. |
| `/resetalerts`    | Clears config and **deletes** the webhook when the bot can still fetch it.                                                                                                                                                                                                      |


Run `/setup` once per server where you want alerts.

## Behavior

- **Bots** do not trigger alerts.
- **Voice state change:** the handler ignores updates where `before.channel == after.channel`, so pure mute/deafen changes in the same channel do not fire; **moving** between voice channels does count as a join to the new channel.
- **Leaving** voice (`after.channel is None`) does not send an alert.
- **Excluded** voice channels: if the joined channel’s ID is in `excluded_channel_ids`, no alert is sent.
- **First in channel:** an alert is sent only when `len(after.channel.members) == 1` right after the join (first human in that voice channel).
- **Message content:** `… just joined … Go say hi …` with [allowed mentions](https://discord.com/developers/docs/resources/channel#allowed-mentions-object) for `@everyone` or the configured role.

## Project layout

- `run_bot.py` — loads `.env`, validates `BOT_TOKEN`, starts the client.
- `utilities/ping_server.py` — intents, `on_voice_state_update`, slash commands, webhook HTTP (`aiohttp`).
- `utilities/config.py` — load/save `utilities/config.json` (JSON parse errors fall back to an empty dict).

## License

[MIT](LICENSE)