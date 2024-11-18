#!/bin/bash

# Script Metadata
#name=Mover Status Script
#description=This script monitors the progress of the "Mover" process and posts updates to a Discord/Telegram webhook.
#backgroundOnly=true
#arrayStarted=true

# Simple timestamp for logs
function log {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Log the starting message
log "Starting Mover Status Monitor..."

# -------------------------------------------
# Script Settings: Edit these!
# -------------------------------------------
# Configure basic settings and webhook details
USE_TELEGRAM=false                                                      # Enable notifications to Telegram
USE_DISCORD=false                                                       # Enable notifications to Discord
TELEGRAM_BOT_TOKEN="xxxx"                                               # Telegram bot token
TELEGRAM_CHAT_ID="xxxx"                                                 # Telegram chat ID
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/xxxx/xxxx"        # Discord webhook URL
DISCORD_NAME_OVERRIDE="Mover Bot"                                       # Display name for Discord notifications
NOTIFICATION_INCREMENT=25                                               # Notification frequency in percentage increments
DRY_RUN=false                                                           # Enable this to test the notifications without actual monitoring
ENABLE_DEBUG=false                                                      # Set to true to enable debug logging

# -------------------------------------------
# Webhook Messages: Edit these if you want
# -------------------------------------------
# Custom messages for each notification point
TELEGRAM_MOVING_MESSAGE="Moving data from SSD Cache to HDD Array. &#10;Progress: <b>{percent}%</b> complete. &#10;Remaining data: {remaining_data}.&#10;Estimated completion time: {etc}.&#10;&#10;Note: Services like Plex may run slow or be unavailable during the move."
DISCORD_MOVING_MESSAGE="Moving data from SSD Cache to HDD Array.\nProgress: **{percent}%** complete.\nRemaining data: {remaining_data}.\nEstimated completion time: {etc}.\n\nNote: Services like Plex may run slow or be unavailable during the move."
COMPLETION_MESSAGE="Moving has been completed!"

# ---------------------------------------
# Exclusion Folders: Define paths to exclude
# ---------------------------------------
# Set EXCLUDE_PATH_XX to directories you want to exclude from being monitored.
# Leave EXCLUDE_PATH_XX variables empty if no exclusions are needed. 
# This will result in monitoring the entire directory specified in the script (/mnt/cache).
#
# Example usage:
# EXCLUDE_PATH_01="/mnt/cache/your/excluded/folder"
# EXCLUDE_PATH_02="/mnt/cache/another/excluded/folder"
# EXCLUDE_PATH_03="/mnt/cache/maybe/a/.hidden/folder"
# Add more EXCLUDE_PATH_XX as needed.

EXCLUDE_PATH_01=""
EXCLUDE_PATH_02=""

# ---------------------------------------------------------
# Advanced Configuration: Only edit if you understand the impact
# ---------------------------------------------------------
# Path to the mover executable
MOVER_EXECUTABLE="/usr/local/sbin/mover"

# ---------------------------------
# Do Not Modify: Script essentials
# ---------------------------------
# Script versioning - check for updates
CURRENT_VERSION="0.0.7"

# Function to check the latest version
function check_latest_version {
    LATEST_VERSION=$(curl -fsSL "https://api.github.com/repos/engels74/mover-status/releases" | jq -r .[0].tag_name)
}

# Initialize to -1 to ensure 0% notification
LAST_NOTIFIED=-1

# Initialize total_data_moved to keep track of the cumulative data moved by the mover process
total_data_moved=0

# ---------------------------------------------------------
# Do Not Modify: Variable checking!
# ---------------------------------------------------------

# Check if at least one notification method is enabled
if ! $USE_TELEGRAM && ! $USE_DISCORD; then
    log "Error: Both USE_TELEGRAM and USE_DISCORD are set to false. At least one must be true."
    exit 1
fi

# Check webhook configurations conditionally
if [[ $USE_TELEGRAM == true ]]; then
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        log "Error: Telegram settings not configured correctly."
        exit 1
    fi
fi

if [[ $USE_DISCORD == true ]]; then
    if ! [[ $DISCORD_WEBHOOK_URL =~ ^https://discord.com/api/webhooks/ ]]; then
        log "Error: Invalid Discord webhook URL."
        exit 1
    fi
fi

# ---------------------------------------------------------
# Do Not Modify: Dry-run check
# ---------------------------------------------------------

if $DRY_RUN; then
    check_latest_version
    log "Running in dry-run mode. No real monitoring will be performed."
    
    # Simulate data for notification
    dry_run_percent=50  # Arbitrary progress percentage for testing
    dry_run_remaining_data="500 GB"  # Arbitrary remaining data amount for testing
    dry_run_datetime=$(date +"%B %d (%Y) - %H:%M:%S")
    dry_run_etc_discord="<t:$(date +%s --date='01/01/2099 12:00'):R>"
    dry_run_etc_telegram="01/01/2099, 12pm"

    # Determine color based on percentage
    if [ "$dry_run_percent" -le 34 ]; then
        dry_run_color=16744576  # Light Red
    elif [ "$dry_run_percent" -le 65 ]; then
        dry_run_color=16753920  # Light Orange
    else
        dry_run_color=9498256   # Light Green
    fi

    # Footer text with version checking
    local footer_text="Version: v${CURRENT_VERSION}"
    if [[ "${LATEST_VERSION}" != "${CURRENT_VERSION}" ]]; then
        footer_text+=" (update available)"
    fi

    # Prepare messages with footer
    dry_run_value_message_discord="Moving data from SSD Cache to HDD Array.\nProgress: **${dry_run_percent}%** complete.\nRemaining data: ${dry_run_remaining_data}.\nEstimated completion time: ${dry_run_etc_discord}.\n\nNote: Services like Plex may run slow or be unavailable during the move."
    dry_run_value_message_telegram="Moving data from SSD Cache to HDD Array. &#10;Progress: <b>${dry_run_percent}%</b> complete. &#10;Remaining data: ${dry_run_remaining_data}.&#10;Estimated completion time: ${dry_run_etc_telegram}.&#10;&#10;Note: Services like Plex may run slow or be unavailable during the move.&#10;&#10${footer_text}"

    # Send test notifications
    if $USE_TELEGRAM; then
        log "Sending test notification to Telegram..."
        dry_run_json_payload=$(jq -n \
                       --arg chat_id "$TELEGRAM_CHAT_ID" \
                       --arg text "$dry_run_value_message_telegram" \
                       '{chat_id: $chat_id, text: $text, disable_notification: "false", parse_mode: "HTML"}')
        /usr/bin/curl -s -o /dev/null -H "Content-Type: application/json" -X POST -d "$dry_run_json_payload" "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage"
    fi

    if $USE_DISCORD; then
        log "Sending test notification to Discord..."
        dry_run_notification_data='{
          "username": "'"$DISCORD_NAME_OVERRIDE"'",
          "content": null,
          "embeds": [
            {
              "title": "Mover: Moving Data",
              "description": "This is a test message from dry-run mode.",
              "color": '"$dry_run_color"',
              "fields": [
                {
                  "name": "'"$dry_run_datetime"'",
                  "value": "'"${dry_run_value_message_discord}"'"
                }
              ],
              "footer": {
                "text": "'"$footer_text"'"
              }
            }
          ]
        }'
        /usr/bin/curl -s -o /dev/null -H "Content-Type: application/json" -X POST -d "$dry_run_notification_data" $DISCORD_WEBHOOK_URL
    fi
    
    log "Dry-run complete. Exiting script."
    exit 0
fi

# ---------------------------------------------------------
# Mover Status Script - Do Not Edit!
# ---------------------------------------------------------

# Prepare exclusion paths for the du command
declare -a exclusion_params
path_index=1
while true; do
    formatted_index=$(printf "%02d" $path_index)
    current_path_var="EXCLUDE_PATH_$formatted_index"
    if [ -z "${!current_path_var}" ]; then
        break
    fi
    if [ ! -d "${!current_path_var}" ]; then
        log "Error: Exclusion path ${!current_path_var} does not exist."
        exit 1
    fi
    exclusion_params+=("--exclude=${!current_path_var}")
    ((path_index++))
done

# Function to convert bytes to human-readable format
function human_readable {
    local bytes=$1
    local tb gb kb mb
    if [ $bytes -ge 1099511627776 ]; then
        tb=$((bytes / 1099511627776))
        remaining_bytes=$((bytes % 1099511627776))
        gb=$((remaining_bytes / 1073741824))
        echo "${tb}.${gb} TB ($((tb * 1024 + gb)) GB)"
    elif [ $bytes -ge 1073741824 ]; then
        gb=$((bytes / 1073741824))
        echo "${gb} GB"
    elif [ $bytes -ge 1048576 ]; then
        mb=$((bytes / 1048576))
        echo "${mb} MB"
    elif [ $bytes -ge 1024 ]; then
        kb=$((bytes / 1024))
        echo "${kb} KB"
    else
        echo "${bytes} Bytes"
    fi
}

# Calculate Estimated Time of Completion
function calculate_etc {
    local percent=$1
    local platform=$2
    local current_time=$(date +%s)
    if [ "$percent" -gt 0 ]; then
        local elapsed=$((current_time - start_time))
        local estimated_total_time=$((elapsed * (total_data_moved + current_size) / total_data_moved))
        local remaining_time=$((estimated_total_time - elapsed))
        local completion_time_estimate=$((current_time + remaining_time))

        if [[ $platform == "discord" ]]; then
            echo "<t:${completion_time_estimate}:R>"
        elif [[ $platform == "telegram" ]]; then
            echo $(date -d "@${completion_time_estimate}" +"%H:%M on %b %d (%Z)")
        fi
    else
        echo "Calculating..."
    fi
}

function send_notification {
    local percent=$1
    local remaining_data=$2
    local datetime=$(date +"%B %d (%Y) - %H:%M:%S")
    local etc_discord=$(calculate_etc $percent "discord")
    local etc_telegram=$(calculate_etc $percent "telegram")

    # Prepare the messages using the predefined templates
    local value_message_discord="${DISCORD_MOVING_MESSAGE//\{percent\}/$percent}"
    value_message_discord="${value_message_discord//\{remaining_data\}/$remaining_data}"
    value_message_discord="${value_message_discord//\{etc\}/$etc_discord}"

    local value_message_telegram="${TELEGRAM_MOVING_MESSAGE//\{percent\}/$percent}"
    value_message_telegram="${value_message_telegram//\{remaining_data\}/$remaining_data}"
    value_message_telegram="${value_message_telegram//\{etc\}/$etc_telegram}"

    local footer_text="Version: v${CURRENT_VERSION}"
    if [[ "${LATEST_VERSION}" != "${CURRENT_VERSION}" ]]; then
        footer_text+=" (update available)"
    fi
    value_message_telegram+="&#10;&#10$footer_text"

    # Determine the color based on completion and percentage
    local color
    if [ "$percent" -ge 100 ] || ! pgrep -x "$(basename $MOVER_EXECUTABLE)" > /dev/null; then
        value_message_discord=$COMPLETION_MESSAGE
        value_message_telegram=$COMPLETION_MESSAGE
        color=65280  # Green for completion
    else
        if [ "$percent" -le 34 ]; then
            color=16744576  # Light Red
        elif [ "$percent" -le 65 ]; then
            color=16753920  # Light Orange
        else
            color=9498256   # Light Green
        fi
    fi

    # Send the notifications
    log "Sending notification..."
    if $USE_TELEGRAM; then
        local json_payload=$(jq -n \
                        --arg chat_id "$TELEGRAM_CHAT_ID" \
                        --arg text "$value_message_telegram" \
                        '{chat_id: $chat_id, text: $text, disable_notification: "false", parse_mode: "HTML"}')
        if $ENABLE_DEBUG; then
            log "Preparing to send to Telegram: $json_payload"
        fi
        local response=$(curl -s -H "Content-Type: application/json" -X POST -d "$json_payload" "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage")
        if $ENABLE_DEBUG; then
            log "Telegram response: $response"
        fi
    fi

    if $USE_DISCORD; then
        local notification_data='{
            "username": "'"$DISCORD_NAME_OVERRIDE"'",
            "content": null,
            "embeds": [
                {
                    "title": "Mover: Moving Data",
                    "color": '"$color"',
                    "fields": [
                        {
                            "name": "'"$datetime"'",
                            "value": "'"${value_message_discord}"'"
                        }
                    ],
                    "footer": {
                        "text": "'"$footer_text"'"
                    }
                }
            ]
        }'
        if $ENABLE_DEBUG; then
            log "Preparing to send to Discord: $notification_data"
        fi
        local response=$(curl -s -H "Content-Type: application/json" -X POST -d "$notification_data" $DISCORD_WEBHOOK_URL -w "\nHTTP status: %{http_code}\nCurl Error: %{errormsg}")
        if $ENABLE_DEBUG; then
            log "Discord response: $response"
        fi
    fi
}

# Main Script Execution Loop
while true; do
    check_latest_version
    log "Monitoring new mover process..."

    # Wait for the mover process to start
    log "Mover process not found, waiting to start monitoring..."
    while ! pgrep -x "$(basename $MOVER_EXECUTABLE)" > /dev/null; do
        sleep 10
    done

    log "Mover process found, starting monitoring..."

    # Calculate initial size after the Mover process is found
    initial_size=$(du -sb "${exclusion_params[@]}" /mnt/cache | cut -f1)
    initial_readable=$(human_readable $initial_size)
    log "Initial total size of data: $initial_readable"

    start_time=$(date +%s)  # Record the start time of monitoring
    log "Monitoring started at: $(date -d "@$start_time" '+%Y-%m-%d %H:%M:%S')"

    percent=0
    send_notification $percent "$initial_readable"  # Send the initial 0% notification
    log "Initial notification sent with 0% completion."

    # Monitor the progress
    while true; do
        current_size=$(du -sb "${exclusion_params[@]}" /mnt/cache | cut -f1)
        remaining_readable=$(human_readable $current_size)

        # Calculate the total data moved and update the percentage
        total_data_moved=$((initial_size - current_size))
        percent=$((total_data_moved * 100 / (total_data_moved + current_size)))

        # Check if the mover process is still running
        if ! pgrep -x "$(basename $MOVER_EXECUTABLE)" > /dev/null; then
            log "Mover process '$(basename $MOVER_EXECUTABLE)' is no longer running."
            log "Total data moved: $total_data_moved bytes, Initial size: $initial_size bytes."
            send_notification 100 "$remaining_readable"
            LAST_NOTIFIED=-1
            log "Final notification sent and monitoring loop exiting."
            break
        fi

        # Send notifications based on increment
        if [ "$((percent / NOTIFICATION_INCREMENT * NOTIFICATION_INCREMENT))" -ge $((LAST_NOTIFIED + NOTIFICATION_INCREMENT)) ]; then
            log "Condition met for sending update: Current percent $percent (rounded down to nearest increment: $((percent / NOTIFICATION_INCREMENT * NOTIFICATION_INCREMENT))) >= Last notified $LAST_NOTIFIED + Increment $NOTIFICATION_INCREMENT"
            send_notification "$percent" "$remaining_readable"
            LAST_NOTIFIED="$((percent / NOTIFICATION_INCREMENT * NOTIFICATION_INCREMENT))"
            log "Notification sent for $percent% completion."
        fi

        sleep 1  # Small delay to prevent excessive CPU usage
    done

    # Delay before restarting monitoring
    log "Restarting monitoring after completion..."
    sleep 10
done

# Mover Status Script
# <https://github.com/engels74/mover-status>
# This script monitors the progress of the "Mover" process and posts updates to a Discord/Telegram webhook.
# Copyright (C) 2024 - engels74
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Contact: engels74@tuta.io
