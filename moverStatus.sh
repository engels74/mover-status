#!/bin/bash

# Exit if running
if [[ $(pidof -x "$(basename "$0")" -o %PPID) ]]; then
    echo "Already running, exiting..."; exit 1
fi

# Script Metadata
#name=Mover Status Script
#description=This script monitors the progress of the "Mover" process and posts updates to a Discord webhook.

# Script Version
CURRENT_VERSION="0.0.3"
LATEST_VERSION=$(curl -fsSL "https://api.github.com/repos/engels74/mover-status/releases" | jq -r .[0].tag_name)

# Environment Variables
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/xxxx/xxxx"
DISCORD_NAME_OVERRIDE="Mover Bot"
MOVER_EXECUTABLE="/usr/local/sbin/mover"
NOTIFICATION_FREQUENCY=120  # Default frequency in seconds (2 minutes)

# User-defined Messages
MOVING_MESSAGE="Moving data from SSD Cache to HDD Array. \nProgress: **{percent}%** complete. \nRemaining data: {remaining_data}.\nEstimated completion time: {etc}\n\n**Note:** Services like Plex may run slow or be unavailable during the move."
COMPLETION_MESSAGE="**Moving has been completed!**"

# User-defined exclusion paths
EXCLUDE_PATH_01="/path/to/excluded/folder"
EXCLUDE_PATH_02=""
# Users can add more EXCLUDE_PATH_XX here as needed

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
        echo "Error: Exclusion path ${!current_path_var} does not exist."
        exit 1
    fi

    exclusion_params+=("--exclude=${!current_path_var}")
    ((path_index++))
done

# Function to convert bytes to human-readable format
human_readable() {
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

# Timestamp for the start of the script
start_time=$(date +%s)
completion_message_sent=false

# Wait for the Mover process to start
while ! pgrep -x "$(basename $MOVER_EXECUTABLE)" > /dev/null; do
    echo "Waiting for the mover process to start..."
    sleep 60
done

# Calculate Estimated Time of Completion
calculate_etc() {
    local percent=$1
    local current_time=$(date +%s)
    local elapsed=$((current_time - start_time))
    if [ "$percent" -gt 0 ]; then
        local estimated_total=$((elapsed * 100 / percent))
        local remaining=$((estimated_total - elapsed))
        echo "<t:$((current_time + remaining)):R>"  # Convert to Discord relative timestamp format
    else
        echo "Calculating..."
    fi
}

# Send Notification Function
send_notification() {
    local percent=$1
    local remaining_data=$2
    local datetime=$(date +"%B %d (%Y) - %H:%M:%S")
    local etc=$(calculate_etc $percent)
    local value_message
    local footer_text

    if [[ "${LATEST_VERSION}" != "${CURRENT_VERSION}" ]]; then
        footer_text="Version: v${CURRENT_VERSION} (update available)"
    else
        footer_text="Version: v${CURRENT_VERSION}"
    fi

    if [ "$percent" -ge 100 ] || ! pgrep -x "$(basename $MOVER_EXECUTABLE)" > /dev/null; then
        value_message=$COMPLETION_MESSAGE
        color=65280  # Green for completion
        completion_message_sent=true
    else
        value_message=$(echo "$MOVING_MESSAGE" | sed "s/{percent}/$percent/g" | sed "s/{remaining_data}/$remaining_data/g" | sed "s/{etc}/$etc/g")
        # Color based on percentage
        if [ "$percent" -le 34 ]; then
            color=16744576  # Light Red
        elif [ "$percent" -le 65 ]; then
            color=16753920  # Light Orange
        else
            color=9498256   # Light Green
        fi
    fi

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
              "value": "'"${value_message}"'"
            }
          ],
          "footer": {
            "text": "'"$footer_text"'"
          }
        }
      ]
    }'

    /usr/bin/curl -H "Content-Type: application/json" -d "$notification_data" $DISCORD_WEBHOOK_URL
}

# Initial Total Size Calculation
initial_size=$(du -sb "${exclusion_params[@]}" /mnt/cache | cut -f1)
initial_readable=$(human_readable $initial_size)

# Tracking Progress
while true; do
    current_size=$(du -sb "${exclusion_params[@]}" /mnt/cache | cut -f1)
    remaining_readable=$(human_readable $current_size)
    percent=$((100 - (current_size * 100 / initial_size)))

    send_notification $percent "$remaining_readable"

    # Send final notification if mover process is no longer running
    if ! pgrep -x "$(basename $MOVER_EXECUTABLE)" > /dev/null; then
        if [ "$completion_message_sent" == "false" ]; then
            send_notification 100 "$remaining_readable"
        fi
        break
    fi

    sleep $NOTIFICATION_FREQUENCY  # Customizable sleep interval
done
