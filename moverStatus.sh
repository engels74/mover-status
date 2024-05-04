#!/bin/bash

#name=Mover Status Script
#description=This script is designed to monitor the progress of the "Mover" process, which it posts to a Discord webhook of your choice.

# Exit if running
if [[ $(pidof -x "$(basename "$0")" -o %PPID) ]]; then
    echo "Already running, exiting..."; exit 1
fi

# Environment Variables
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/xxxx/xxxx"
DISCORD_NAME_OVERRIDE="Mover Bot"
MOVER_EXECUTABLE="/usr/local/sbin/mover"
NOTIFICATION_FREQUENCY=120  # Default frequency in seconds (2 minutes)

# User-defined exclusion paths
EXCLUDE_PATH_01="/path/to/excluded/folder"
EXCLUDE_PATH_02=""
EXCLUDE_PATH_03=""
EXCLUDE_PATH_04=""
EXCLUDE_PATH_05=""
# Users can add more EXCLUDE_PATH_XX here as needed

# Prepare exclusion paths for the du command
exclusion_string=""
path_index=1

while true; do
    # Format the index with leading zero for numbers less than 10
    formatted_index=$(printf "%02d" $path_index)
    current_path_var="EXCLUDE_PATH_$formatted_index"

    # Break the loop if the variable is not set or empty
    if [ -z "${!current_path_var}" ]; then
        break
    fi

    # Check if the directory exists
    if [ ! -d "${!current_path_var}" ]; then
        echo "Error: Exclusion path ${!current_path_var} does not exist."
        exit 1
    fi

    # Add the exclude option to the command string
    exclusion_string+=" --exclude='${!current_path_var}'"
    ((path_index++))
done

# Function to convert bytes to human-readable format and add GB equivalent for TB
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

    if [ "$percent" -ge 100 ] || ! pgrep -x "$(basename $MOVER_EXECUTABLE)" > /dev/null; then
        value_message="**Moving has been completed!**"
        color=65280  # Green for completion
        completion_message_sent=true
    else
        value_message="**Status:** Moving data from SSD Cache to HDD Array. \nProgress: **${percent}%** complete. \nRemaining data: ${remaining_data}.\nEstimated completion time: ${etc}\n\n**Note:** Services like Plex may run slow or be unavailable during the move."
        # Color based on percentage
        if [ "$percent" -le 35 ]; then
            color=16744576  # Light Red: #FF6666
        elif [ "$percent" -le 50 ]; then
            color=65535  # Light Blue: #87CEEB (Sky Blue)
        elif [ "$percent" -lt 100 ]; then
            color=9498256  # Light Green: #90EE90
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
          ]
        }
      ]
    }'

    /usr/bin/curl -H "Content-Type: application/json" -d "$notification_data" $DISCORD_WEBHOOK_URL
}

# Initial Total Size Calculation
initial_size=$(du -sb $exclusion_string /mnt/cache | cut -f1)
initial_readable=$(human_readable $initial_size)

# Tracking Progress
while true; do
    current_size=$(du -sb $exclusion_string /mnt/cache | cut -f1)
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
