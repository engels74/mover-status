# Mover Status 🚚

<p align="center">
  <img src="https://i.imgur.com/51gQKps.png" alt="MoverStatus Script"/>
</p>

### Description 📜
This Bash script monitors the progress of the "Mover" process and sends updates to Discord and/or Telegram webhooks. It provides real-time notifications on the status of the data moving process from SSD Cache to HDD Array.

### How it works ⚙️
1. When the script runs, it continuously loops and waits for the Unraid Mover script to start.
2. Once it detects the Unraid Mover script, it posts the initial notification to your Discord or Telegram webhook.
3. It calculates the total amount of data on your cache, excluding the paths you specify. The estimation of the remaining time can vary.
4. You can exclude specific folders from the mover process, such as those used by other applications like qBittorrent and SABnzbd, or any hidden folders.
5. The script posts a progress update based on the percentage of data moved, configurable via the `NOTIFICATION_INCREMENT` setting.
6. If the mover process completes successfully, the script posts a final notification indicating 100% completion and exits.
7. If the mover process stops unexpectedly, the script detects this and sets the completion status to 100%, posting the final notification accordingly.

### Installation 🛠️
I'm using the UnraidOS plugin named "[User Scripts](https://forums.unraid.net/topic/48286-plugin-ca-user-scripts/)"
1. Go into "**Settings**"
2. Select "**User Scripts**"
3. Select "**Add New Script**"
4. Name your script "**Mover Status**" (or anything else)
5. Select/hover the **Settings Wheel** icon of the Mover Status script you just created
6. Select "**Edit Script**"
7. Copy everything from the [moverStatus.sh](https://raw.githubusercontent.com/engels74/mover-status/main/moverStatus.sh) into the file 
8. Edit the variables at the top to your liking (you don't **have** to define any excluded folders - leave them empty if you don't need to exclude folders)
9. Select "**Save Changes**" to save the script
10. Cron-jobs does NOT work with this script

### Script Settings ⚙️
Edit the script to configure the necessary settings:

- `USE_TELEGRAM`: Set to `true` to enable Telegram notifications.
- `USE_DISCORD`: Set to `true` to enable Discord notifications.
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token.
- `TELEGRAM_CHAT_ID`: Your Telegram group or channel chat ID.
- `DISCORD_WEBHOOK_URL`: Your Discord webhook URL.
- `DISCORD_NAME_OVERRIDE`: The display name for Discord notifications.
- `NOTIFICATION_INCREMENT`: The frequency of notifications in percentage increments.
- `DRY_RUN`: Set to `true` to test notifications without actual monitoring.
- `ENABLE_DEBUG`: Set to `true` to enable debug logging.

### Telegram Bot Setup 🤖

1. **Create a Telegram Bot**:
    - Open Telegram and search for the user `@BotFather`.
    - Start a chat with `@BotFather` and send the command `/start`.
    - To create a new bot, send the command `/newbot`.
    - Follow the instructions to name your bot and receive your bot token.
    - Save the bot token for later use.

2. **Invite the Bot to Your Group or Channel**:
    - Create a new group or channel in Telegram.
    - Invite your bot to the group or channel. Make sure to promote it to an admin if you want it to have full access to send messages.

3. **Send a Message in the Group or Channel**:
    - Send any message in the group or channel to generate activity that the bot can access.

4. **Get Your Telegram Group or Channel Chat ID**:
    - Visit the following URL in your web browser, replacing `YOUR_BOT_TOKEN` with your actual bot token:
      ```
      https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
      ```
    - Look for the `chat` object in the JSON response to find your `TELEGRAM_CHAT_ID`. For example, in the response:
      ```json
      {
        "ok": true,
        "result": [
          {
            "update_id": 123456789,
            "message": {
              "chat": {
                "id": -1001122334455,
                "title": "Your Group or Channel Name",
                "type": "supergroup"
              }
            }
          }
        ]
      }
      ```

  The `TELEGRAM_CHAT_ID` would then be `-1001122334455`.

### Discord Webhook Setup 🖥️

1. Go to your Discord server settings.
2. Navigate to the "Integrations" section and click "Webhooks".
3. Click "New Webhook" and configure it.
4. Copy the Webhook URL.
5. The webhook URL can be used for `DISCORD_WEBHOOK_URL`.

## Images (preview) 📸
<img src="https://i.imgur.com/owBzb5R.png" width="50%" alt="An example of how it looks">
