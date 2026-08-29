# Mover Status 

<p align="center">
  <img src="mover-status.svg" alt="base-image" style="width: 40%;"/>
</p>

<p align="center">
  <a href="https://github.com/engels74/mover-status/releases"><img src="https://img.shields.io/github/v/tag/engels74/mover-status?sort=semver" alt="GitHub tag (SemVer)"></a>
  <a href="https://github.com/engels74/mover-status/blob/main/LICENSE"><img src="https://img.shields.io/github/license/engels74/mover-status" alt="License"></a>
  <a href="https://github.com/engels74/mover-status/stargazers"><img src="https://img.shields.io/github/stars/engels74/mover-status.svg" alt="GitHub Stars"></a>
  <a href="https://endsoftwarepatents.org/innovating-without-patents"><img style="height: 20px;" src="https://static.fsf.org/nosvn/esp/logos/patent-free.svg"></a>
</p>

## 📑 Table of Contents
- [📜 Description](#-description)
- [📸 Images (preview)](#-images-preview)
- [⚙️ How it works](#-how-it-works)
- [🛠️ Installation](#-installation)
- [🔄 Mover Tuning Plugin](#-mover-tuning-plugin)
- [⏰❌ Why can't I use cron/scheduling for this script?!](#-why-cant-i-use-cronscheduling-for-this-script)
- [🔄 Can I make the script start on startup/reboot?](#-can-i-make-the-script-start-on-startupreboot)
- [⚙️ Script Settings](#-script-settings)
- [🤖 Telegram Bot Setup](#-telegram-bot-setup)
- [🖥️ Discord Webhook Setup](#-discord-webhook-setup)
- [📲 Pushover Setup](#-pushover-setup)
- [📣 Apprise Setup](#-apprise-setup)
- [🐛 Reporting Issues](#-reporting-issues)
- [⚖️ License](#-license)

### 📜 Description 
This Bash script monitors the progress of the "Mover" process and sends updates to Discord, Telegram, Pushover, and/or Apprise. It provides real-time notifications on the status of the data moving process from SSD Cache to HDD Array.

## 📸 Images (preview) 
<img src="https://i.imgur.com/owBzb5R.png" width="60%" alt="An example of how it looks">

### ⚙️ How it works 
1. When the script runs, it continuously loops and waits for the Unraid Mover script to start.
2. Once it detects the Unraid Mover script, it posts the initial notification to your enabled notification service(s).
3. It calculates the total amount of data on your cache, excluding the paths you specify. The estimation of the remaining time can vary.
4. You can exclude specific folders from the mover process, such as those used by other applications like qBittorrent and SABnzbd, or any hidden folders.
5. The script posts a progress update based on the percentage of data moved, configurable via the `NOTIFICATION_INCREMENT` setting.
6. If the mover process completes successfully, the script posts a final notification indicating 100% completion and exits.
7. If the mover process stops unexpectedly, the script detects this and sets the completion status to 100%, posting the final notification accordingly.

### 🛠️ Installation 
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
10. Use **Run in Background** to run the script
11. Cron-jobs should **NOT** be used with the script

### 🔄 Mover Tuning Plugin
If you are using the "Mover Tuning" plugin for Unraid, please ensure you have the latest version installed. The old version has been removed from the Unraid app/plugin store and will not be auto-removed. Users must manually update to [the new version](https://unraid.net/community/apps?q=mover+tuning#r).

<p align="center">
  <img src="https://up.shx.gg/71UMT4Sbk.png" alt="New Mover Tuning Plugin" width="60%">
</p>

### ⏰❌ Why can't I use cron/scheduling for this script?! 
The Unraid "User Scripts" plugin uses a "lockfile" to prevent multiple instances of a script running simultaneously. Adding our own "lockfile" function to the script itself, causes the plugin to lose track of the script, making it appear as if it's not running, even though it is running correctly in the background. 
Because the script runs in a loop, I've yet to find a way to integrate it with cron/scheduling while maintaining compatibility with the User Scripts plugin.

### 🔄 Can I make the script start on startup/reboot? 
Well, somewhat! You can make it start, whenever you start up your Unraid array
1. Go into "**Settings**"
2. Select "**User Scripts**"
3. Find the Mover Status script
4. To the right, click on the "**Schedule disabled**"
5. Select "**At Startup of Array**" ([screenshot](<https://i.imgur.com/2rtkxuM.png>))
6. Press the "**Apply**" to save the change
7. Select "**Done**"
8. The script will now launch automatically, when you start your array!

### ⚙️ Script Settings 
Edit the script to configure the necessary settings:

- `USE_TELEGRAM`: Set to `true` to enable Telegram notifications.
- `USE_DISCORD`: Set to `true` to enable Discord notifications.
- `USE_PUSHOVER`: Set to `true` to enable Pushover notifications.
- `USE_APPRISE`: Set to `true` to enable Apprise notifications.
- `APPRISE_MODE`: Select `cli` for the local Apprise CLI or `api` for an Apprise API server.
- `APPRISE_BIN`: Path to the local Apprise executable when using CLI mode.
- `APPRISE_API_URL`: Base URL of the Apprise API server when using API mode.
- `APPRISE_TITLE`: Notification title used for Apprise messages.
- `APPRISE_TARGETS`: One or more Apprise notification URLs. Each target is delivered and retried independently.
- `APPRISE_MOVING_MESSAGE`: Optional custom Apprise progress-message template.
- `APPRISE_COMPLETION_MESSAGE`: Optional custom Apprise completion-message template.
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token.
- `TELEGRAM_CHAT_ID`: Your Telegram group or channel chat ID.
- `DISCORD_WEBHOOK_URL`: Your Discord webhook URL.
- `DISCORD_NAME_OVERRIDE`: The display name for Discord notifications.
- `PUSHOVER_APP_TOKEN`: Your Pushover application/API token.
- `PUSHOVER_USER_KEY`: Your Pushover user or group key.
- `PUSHOVER_TITLE`: The title used for Pushover notifications.
- `NOTIFICATION_INCREMENT`: The frequency of notifications in percentage increments.
- `DRY_RUN`: Set to `true` to test notifications without actual monitoring.
- `ENABLE_DEBUG`: Set to `true` to enable debug logging.

### 🤖 Telegram Bot Setup 

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

### 🖥️ Discord Webhook Setup 

1. Go to your Discord server settings.
2. Navigate to the "Integrations" section and click "Webhooks".
3. Click "New Webhook" and configure it.
4. Copy the Webhook URL.
5. The webhook URL can be used for `DISCORD_WEBHOOK_URL`.

### 📲 Pushover Setup

1. Sign in to Pushover and register an application/API token.
2. Copy the application token into `PUSHOVER_APP_TOKEN`.
3. Copy your Pushover user key (or a group key) into `PUSHOVER_USER_KEY`.
4. Set `USE_PUSHOVER=true`.
5. Optionally change `PUSHOVER_TITLE` to customize the notification title.
6. Set `DRY_RUN=true` to send a test notification without monitoring Mover.

### 📣 Apprise Setup

[Apprise](https://github.com/caronc/apprise) provides a common notification interface for many different services. Mover Status supports Apprise in two modes: a local CLI and the Apprise HTTP API.

#### Enable Apprise

```bash
USE_APPRISE=true
APPRISE_MODE="cli"                    # cli | api

APPRISE_BIN="/usr/bin/apprise"
APPRISE_API_URL="http://127.0.0.1:8000"
APPRISE_TITLE="Mover Status"

APPRISE_TARGETS=(
    "pover://USER_KEY@APP_TOKEN"
)
```

`pover://` is only a Pushover example. `APPRISE_TARGETS` accepts normal Apprise notification URLs for services supported by Apprise.

Multiple destinations can be configured:

```bash
APPRISE_TARGETS=(
    "pover://USER_KEY@APP_TOKEN"
    "discord://WEBHOOK_ID/WEBHOOK_TOKEN"
    "ntfys://ntfy.sh/my-topic"
)
```

Mover Status sends each target independently. If one target fails, successful targets are not blocked or resent during retries of the failed target.

#### CLI mode

Set:

```bash
APPRISE_MODE="cli"
APPRISE_BIN="/usr/bin/apprise"
```

CLI mode requires a working Apprise executable on the Unraid host. The default path is `/usr/bin/apprise`.

You can verify the CLI manually with:

```bash
apprise --version
```

#### API mode

Set:

```bash
APPRISE_MODE="api"
APPRISE_API_URL="http://127.0.0.1:8000"
```

API mode sends stateless notification requests to the Apprise API `/notify` endpoint. The API server may run locally or on another reachable host.

A minimal local-only Apprise API Docker deployment looks like:

```bash
docker run -d \
  --name apprise \
  -p 127.0.0.1:8000:8000 \
  -e APPRISE_WORKER_COUNT=1 \
  caronc/apprise:latest
```

You can verify that the API is reachable with:

```bash
curl -fsS http://127.0.0.1:8000/status
```

#### Testing

Set:

```bash
DRY_RUN=true
```

and run Mover Status. A successful Apprise delivery exits normally. If an Apprise target cannot be delivered, dry-run exits with a non-zero status.

#### Security notes

Apprise notification URLs may contain credentials.

In CLI mode, the target URL is passed to the Apprise executable as a command-line argument and may therefore be briefly visible to other sufficiently privileged processes on the host.

In API mode, Mover Status sends the target URL inside the JSON request body rather than as a `curl` command-line argument. The Apprise API endpoint itself is still visible in the process command line. The Docker example above binds the API to loopback only. If you use a remote Apprise API, protect the connection appropriately because notification URLs may contain credentials.

### 🐛 Reporting Issues

If you encounter any issues or have feature requests, please create a new issue on GitHub by following these steps:

1. Go to the [Issues](https://github.com/engels74/mover-status/issues) tab in the repository.
2. Click on **New Issue**.
3. Select the appropriate issue template and fill out the required details.
4. Submit the issue.

**Note:** Please **do not** reach out for support via Discord, as there is no official Discord server for this project. All support requests should be submitted as GitHub issues.

## ⚖️ License

[![GNU AGPLv3 Image](https://www.gnu.org/graphics/agplv3-155x51.png)](https://www.gnu.org/licenses/agpl-3.0.en.html)

This project is licensed under the AGPLv3 License - see the LICENSE file for details.
