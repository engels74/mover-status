#!/bin/bash

# Script Metadata
#name=Mover Status Script
#description=This script monitors the progress of the "Mover" process and posts updates to a Discord/Telegram webhook.
#backgroundOnly=true
#arrayStarted=true

# ---------------------------------------------------------
# Mover Status Script
# ---------------------------------------------------------
# Monitors Unraid's mover process and posts progress updates
# to Discord and/or Telegram webhooks.
#
# Dependencies: bash, curl, jq, du, pgrep, date
# Runs as a backgroundOnly Unraid user script.
# ---------------------------------------------------------

# Simple timestamp for logs
log() {
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
DU_POLL_INTERVAL=30                                                     # Seconds between disk usage recalculations (higher = less I/O load)
CACHE_PATH="/mnt/cache"                                                 # Path to cache directory to monitor
ENABLE_FILE_INFO=false                                                  # Show file count and current file in notifications (requires Mover Tuning plugin)

# -------------------------------------------
# Webhook Messages: Edit these if you want
# -------------------------------------------
# Custom messages for each notification point
TELEGRAM_MOVING_MESSAGE="Moving data from SSD Cache to HDD Array. &#10;Progress: <b>{percent}%</b> complete. &#10;Remaining data: {remaining_data}.&#10;Estimated completion time: {etc}.&#10;&#10;Note: Services like Plex may run slow or be unavailable during the move."
DISCORD_MOVING_MESSAGE="Moving data from SSD Cache to HDD Array.\nProgress: **{percent}%** complete.\nRemaining data: {remaining_data}.\nEstimated completion time: {etc}.\n\nNote: Services like Plex may run slow or be unavailable during the move."
COMPLETION_MESSAGE="Moving has been completed!"
DISCORD_COMPLETION_MESSAGE=""                                           # If empty, falls back to COMPLETION_MESSAGE
TELEGRAM_COMPLETION_MESSAGE=""                                          # If empty, falls back to COMPLETION_MESSAGE

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

# shellcheck disable=SC2034
EXCLUDE_PATH_01=""
# shellcheck disable=SC2034
EXCLUDE_PATH_02=""

# ---------------------------------
# Do Not Modify: Script essentials
# ---------------------------------
# Script versioning - check for updates
CURRENT_VERSION="0.0.8"

# Function to check the latest version
check_latest_version() {
    LATEST_VERSION=$(curl -fsSL --connect-timeout 5 --max-time 10 "https://api.github.com/repos/engels74/mover-status/releases" | jq -r .[0].tag_name) || LATEST_VERSION=""
}

# Initialize to -1 to ensure 0% notification
LAST_NOTIFIED=-1

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
    if ! [[ $DISCORD_WEBHOOK_URL =~ ^https://(discord\.com|discordapp\.com)/api/webhooks/ ]]; then
        log "Error: Invalid Discord webhook URL."
        exit 1
    fi
fi

# Validate DU_POLL_INTERVAL is a positive integer
if ! [[ "$DU_POLL_INTERVAL" =~ ^[0-9]+$ ]] || [ "$DU_POLL_INTERVAL" -eq 0 ]; then
    log "Error: DU_POLL_INTERVAL must be a positive integer. Got: '$DU_POLL_INTERVAL'"
    exit 1
fi

# Validate CACHE_PATH exists
if [ ! -d "$CACHE_PATH" ]; then
    log "Error: CACHE_PATH directory does not exist: '$CACHE_PATH'"
    exit 1
fi

# Check latest version once at startup (after validation so we don't hit the API on misconfiguration)
LATEST_VERSION=""
check_latest_version

# ---------------------------------------------------------
# Do Not Modify: Dry-run check
# ---------------------------------------------------------

if $DRY_RUN; then
    log "Running in dry-run mode. No real monitoring will be performed."

    # Detect data source for informational purposes
    if [ -f "/usr/local/emhttp/state/mover.ini" ] && grep -q "TotalToSecondary" "/usr/local/emhttp/state/mover.ini" 2>/dev/null; then
        log "Dry-run: mover.ini detected (Mover Tuning plugin available)"
        dry_run_data_source="mover_ini"
    else
        log "Dry-run: Using du polling mode (no mover.ini found)"
        dry_run_data_source="du_polling"
    fi

    # Simulate data for notification
    dry_run_percent=50  # Arbitrary progress percentage for testing
    dry_run_remaining_data="500 GB"  # Arbitrary remaining data amount for testing
    dry_run_datetime=$(date +"%B %d (%Y) - %H:%M:%S")
    dry_run_etc_discord="<t:$(date +%s --date='01/01/2099 12:00'):R>"
    dry_run_etc_telegram="01/01/2099, 12pm"

    # Simulate file info if available
    dry_run_file_count=""
    dry_run_current_file=""
    if $ENABLE_FILE_INFO && [ "$dry_run_data_source" = "mover_ini" ]; then
        dry_run_file_count="898/1796 files"
        dry_run_current_file="/mnt/cache/share/example_file.txt"
    fi

    # Determine color based on percentage
    if [ "$dry_run_percent" -le 34 ]; then
        dry_run_color=16744576  # Light Red
    elif [ "$dry_run_percent" -le 65 ]; then
        dry_run_color=16753920  # Light Orange
    else
        dry_run_color=9498256   # Light Green
    fi

    # Footer text with version checking
    footer_text="Version: v${CURRENT_VERSION}"
    if [[ -n "${LATEST_VERSION}" && "${LATEST_VERSION}" != "${CURRENT_VERSION}" ]]; then
        footer_text+=" (update available)"
    fi

    # Prepare messages with placeholders
    dry_run_value_message_discord="${DISCORD_MOVING_MESSAGE//\{percent\}/$dry_run_percent}"
    dry_run_value_message_discord="${dry_run_value_message_discord//\{remaining_data\}/$dry_run_remaining_data}"
    dry_run_value_message_discord="${dry_run_value_message_discord//\{etc\}/$dry_run_etc_discord}"
    dry_run_value_message_discord="${dry_run_value_message_discord//\{file_count\}/$dry_run_file_count}"
    dry_run_value_message_discord="${dry_run_value_message_discord//\{current_file\}/$dry_run_current_file}"

    dry_run_value_message_telegram="${TELEGRAM_MOVING_MESSAGE//\{percent\}/$dry_run_percent}"
    dry_run_value_message_telegram="${dry_run_value_message_telegram//\{remaining_data\}/$dry_run_remaining_data}"
    dry_run_value_message_telegram="${dry_run_value_message_telegram//\{etc\}/$dry_run_etc_telegram}"
    dry_run_value_message_telegram="${dry_run_value_message_telegram//\{file_count\}/$dry_run_file_count}"
    dry_run_value_message_telegram="${dry_run_value_message_telegram//\{current_file\}/$dry_run_current_file}"
    dry_run_value_message_telegram+="&#10;&#10;${footer_text}"

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
              "description": "This is a test message from dry-run mode (data source: '"$dry_run_data_source"').",
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
        /usr/bin/curl -s -o /dev/null -H "Content-Type: application/json" -X POST -d "$dry_run_notification_data" "$DISCORD_WEBHOOK_URL"
    fi

    log "Dry-run complete. Exiting script."
    exit 0
fi

# ---------------------------------------------------------
# Mover Status Script - Do Not Edit!
# ---------------------------------------------------------

# Prepare exclusion paths for the du command
declare -a exclusion_params
for var_name in "${!EXCLUDE_PATH_@}"; do
    if [ -n "${!var_name}" ]; then
        if [ ! -d "${!var_name}" ]; then
            log "Error: Exclusion path '${!var_name}' (${var_name}) does not exist."
            exit 1
        fi
        exclusion_params+=("--exclude=${!var_name}")
    fi
done

# Check if any mover-related process is running (supports Unraid v7+ and Mover Tuning plugin)
is_mover_running() {
    pgrep -x "mover" > /dev/null 2>&1 && return 0
    pgrep -x "age_mover" > /dev/null 2>&1 && return 0
    pgrep -f "^/usr/libexec/unraid/move" > /dev/null 2>&1 && return 0
    return 1
}

# Mover.ini path (written by Mover Tuning plugin's age_mover)
MOVER_INI_PATH="/usr/local/emhttp/state/mover.ini"

# State persistence paths
STATE_DIR="/tmp/mover-status"
STATE_FILE="${STATE_DIR}/state"
LAST_RUN_FILE="${STATE_DIR}/last-run"

# Global data source identifier: "mover_ini" or "du_polling"
DATA_SOURCE=""

# Progress globals (set by get_progress)
PROGRESS_PERCENT=0
PROGRESS_REMAINING_BYTES=0
PROGRESS_MOVED_BYTES=0
PROGRESS_TOTAL_BYTES=0
PROGRESS_FILE_COUNT=""
PROGRESS_REMAIN_FILES=""
PROGRESS_CURRENT_FILE=""

# INI globals (set by read_mover_ini)
INI_TOTAL_TO_SECONDARY=0
INI_REMAIN_TO_SECONDARY=0
INI_TOTAL_FILES=0
INI_REMAIN_FILES=0
INI_CURRENT_FILE=""
INI_ACTION=""

# Detect whether mover.ini is available and usable
detect_data_source() {
    if [ -f "$MOVER_INI_PATH" ] && grep -q "TotalToSecondary" "$MOVER_INI_PATH" 2>/dev/null; then
        DATA_SOURCE="mover_ini"
        log "Data source: mover.ini (Mover Tuning plugin detected)"
    else
        DATA_SOURCE="du_polling"
        log "Data source: du polling (standard mover)"
    fi
}

# Parse mover.ini into INI_* globals
read_mover_ini() {
    if [ ! -f "$MOVER_INI_PATH" ]; then
        log "Warning: mover.ini not found at $MOVER_INI_PATH"
        return 1
    fi

    local key value
    # shellcheck disable=SC2034
    while IFS='=' read -r key value; do
        # Remove surrounding quotes from value
        value="${value%\"}"
        value="${value#\"}"
        case "$key" in
            TotalToSecondary)  INI_TOTAL_TO_SECONDARY="$value" ;;
            RemainToSecondary) INI_REMAIN_TO_SECONDARY="$value" ;;
            TotalFilesToSecondary)  INI_TOTAL_FILES="$value" ;;
            RemainFilesToSecondary) INI_REMAIN_FILES="$value" ;;
            File)   INI_CURRENT_FILE="$value" ;;
            Action) INI_ACTION="$value" ;;
        esac
    done < "$MOVER_INI_PATH"

    # Staleness check: warn if file hasn't been modified in >3x DU_POLL_INTERVAL
    local mod_time current_time age stale_threshold
    mod_time=$(stat -c %Y "$MOVER_INI_PATH" 2>/dev/null) || return 0
    current_time=$(date +%s)
    age=$((current_time - mod_time))
    stale_threshold=$((DU_POLL_INTERVAL * 3))
    if [ "$age" -gt "$stale_threshold" ]; then
        log "Warning: mover.ini hasn't been updated in ${age}s (threshold: ${stale_threshold}s) — plugin may have stalled"
    fi

    return 0
}

# Unified progress reader — sets PROGRESS_* globals from either data source
get_progress() {
    if [ "$DATA_SOURCE" = "mover_ini" ]; then
        read_mover_ini || return 1

        PROGRESS_TOTAL_BYTES="$INI_TOTAL_TO_SECONDARY"
        PROGRESS_REMAINING_BYTES="$INI_REMAIN_TO_SECONDARY"
        PROGRESS_MOVED_BYTES=$((INI_TOTAL_TO_SECONDARY - INI_REMAIN_TO_SECONDARY))
        if [ "$PROGRESS_MOVED_BYTES" -lt 0 ]; then
            PROGRESS_MOVED_BYTES=0
        fi

        if [ "$PROGRESS_TOTAL_BYTES" -gt 0 ]; then
            PROGRESS_PERCENT=$((PROGRESS_MOVED_BYTES * 100 / PROGRESS_TOTAL_BYTES))
        else
            PROGRESS_PERCENT=0
        fi

        PROGRESS_FILE_COUNT="$INI_TOTAL_FILES"
        PROGRESS_REMAIN_FILES="$INI_REMAIN_FILES"
        PROGRESS_CURRENT_FILE="$INI_CURRENT_FILE"
    else
        # du_polling mode — uses current_size and initial_size (set in main loop)
        local current_du
        current_du=$(du -sb "${exclusion_params[@]}" "$CACHE_PATH" | cut -f1)

        PROGRESS_REMAINING_BYTES="$current_du"
        PROGRESS_TOTAL_BYTES="$initial_size"
        PROGRESS_MOVED_BYTES=$((initial_size - current_du))
        if [ "$PROGRESS_MOVED_BYTES" -lt 0 ]; then
            PROGRESS_MOVED_BYTES=0
        fi

        if [ "$initial_size" -gt 0 ]; then
            PROGRESS_PERCENT=$((PROGRESS_MOVED_BYTES * 100 / initial_size))
            if [ "$PROGRESS_PERCENT" -lt 0 ]; then
                PROGRESS_PERCENT=0
            elif [ "$PROGRESS_PERCENT" -gt 99 ]; then
                PROGRESS_PERCENT=99
            fi
        else
            PROGRESS_PERCENT=0
        fi

        PROGRESS_FILE_COUNT=""
        PROGRESS_REMAIN_FILES=""
        PROGRESS_CURRENT_FILE=""
    fi

    return 0
}

# Get mover PID from pid file or pgrep
get_mover_pid() {
    local pid
    if [ -f "/var/run/mover.pid" ]; then
        pid=$(cat /var/run/mover.pid 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        fi
    fi
    # Fallback to pgrep
    pid=$(pgrep -x "mover" 2>/dev/null || pgrep -x "age_mover" 2>/dev/null || pgrep -f "^/usr/libexec/unraid/move" 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    fi
    return 1
}

# Get mover process start time as epoch seconds
get_mover_start_time() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    # Use stat on /proc/<pid> to get process start time (Linux-specific)
    local start_time
    start_time=$(stat -c %Y "/proc/${pid}" 2>/dev/null)
    if [ -n "$start_time" ]; then
        echo "$start_time"
        return 0
    fi
    return 1
}

# Create state directory if missing
init_state_dir() {
    if [ ! -d "$STATE_DIR" ]; then
        mkdir -p "$STATE_DIR"
        if $ENABLE_DEBUG; then
            log "Created state directory: $STATE_DIR"
        fi
    fi
}

# Atomically write tracking state to state file
save_state() {
    local tmp_file="${STATE_FILE}.tmp"
    cat > "$tmp_file" <<EOF
STATE_VERSION=1
DATA_SOURCE=${DATA_SOURCE}
MOVER_PID=${mover_pid}
MOVER_START_TIME=${mover_start_time}
SCRIPT_START_TIME=${start_time}
INITIAL_SIZE=${initial_size}
LAST_PERCENT=${PROGRESS_PERCENT}
LAST_NOTIFIED=${LAST_NOTIFIED}
LAST_REMAINING_BYTES=${PROGRESS_REMAINING_BYTES}
LAST_MOVED_BYTES=${PROGRESS_MOVED_BYTES}
LAST_POLL_TIME=$(date +%s)
TOTAL_FILES=${PROGRESS_FILE_COUNT}
EOF
    mv "$tmp_file" "$STATE_FILE"
}

# Read saved state, validate PID matches running mover
# Returns 0 if state is valid and can be resumed, 1 otherwise
load_state() {
    if [ ! -f "$STATE_FILE" ]; then
        if $ENABLE_DEBUG; then
            log "No saved state file found"
        fi
        return 1
    fi

    # Source the state file
    # shellcheck source=/dev/null
    . "$STATE_FILE"

    # Validate state version
    if [ "${STATE_VERSION:-0}" != "1" ]; then
        log "State file has unknown version: ${STATE_VERSION:-missing}"
        rm -f "$STATE_FILE"
        return 1
    fi

    # Check if the saved mover PID is still running
    # Note: MOVER_PID, INITIAL_SIZE, SCRIPT_START_TIME, MOVER_START_TIME
    # are sourced from the state file above
    local current_pid
    current_pid=$(get_mover_pid) || return 1

    # shellcheck disable=SC2153
    if [ "$MOVER_PID" != "$current_pid" ]; then
        if $ENABLE_DEBUG; then
            log "Saved mover PID ($MOVER_PID) doesn't match current ($current_pid)"
        fi
        rm -f "$STATE_FILE"
        return 1
    fi

    # Restore globals from sourced state file values
    # shellcheck disable=SC2153
    initial_size="$INITIAL_SIZE"
    # shellcheck disable=SC2153
    start_time="$SCRIPT_START_TIME"
    # LAST_NOTIFIED is already set by sourcing the state file
    mover_pid="$MOVER_PID"
    # shellcheck disable=SC2153
    mover_start_time="$MOVER_START_TIME"

    log "Resumed from saved state (mover PID: $mover_pid, last notified: ${LAST_NOTIFIED}%)"
    return 0
}

# Write final stats to last-run file, remove active state
save_last_run() {
    local end_time duration
    end_time=$(date +%s)
    duration=$((end_time - start_time))

    cat > "$LAST_RUN_FILE" <<EOF
COMPLETED_AT=${end_time}
DURATION=${duration}
TOTAL_BYTES=${PROGRESS_TOTAL_BYTES}
MOVED_BYTES=${PROGRESS_MOVED_BYTES}
DATA_SOURCE=${DATA_SOURCE}
TOTAL_FILES=${PROGRESS_FILE_COUNT}
EOF

    rm -f "$STATE_FILE"
    if $ENABLE_DEBUG; then
        log "Saved last-run stats and cleared active state"
    fi
}

# Convert seconds to human-readable duration (e.g., "3h 42m")
format_duration() {
    local seconds=$1
    local hours minutes

    if [ "$seconds" -ge 3600 ]; then
        hours=$((seconds / 3600))
        minutes=$(( (seconds % 3600) / 60 ))
        echo "${hours}h ${minutes}m"
    elif [ "$seconds" -ge 60 ]; then
        minutes=$((seconds / 60))
        echo "${minutes}m"
    else
        echo "${seconds}s"
    fi
}

# Convert bytes/sec to human-readable speed string (e.g., "219 MB/s")
format_speed() {
    local bytes_per_sec=$1

    if [ "$bytes_per_sec" -ge 1073741824 ]; then
        local gb=$((bytes_per_sec / 1073741824))
        echo "${gb} GB/s"
    elif [ "$bytes_per_sec" -ge 1048576 ]; then
        local mb=$((bytes_per_sec / 1048576))
        echo "${mb} MB/s"
    elif [ "$bytes_per_sec" -ge 1024 ]; then
        local kb=$((bytes_per_sec / 1024))
        echo "${kb} KB/s"
    else
        echo "${bytes_per_sec} B/s"
    fi
}

# Build rich completion message with all available stats
# Sets COMPLETION_SUMMARY_DISCORD and COMPLETION_SUMMARY_TELEGRAM
build_completion_summary() {
    local end_time duration avg_speed_val
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    local duration_str
    duration_str=$(format_duration "$duration")
    local total_moved_str
    total_moved_str=$(human_readable "$PROGRESS_MOVED_BYTES")

    local avg_speed_str="N/A"
    if [ "$duration" -gt 0 ] && [ "$PROGRESS_MOVED_BYTES" -gt 0 ]; then
        avg_speed_val=$((PROGRESS_MOVED_BYTES / duration))
        avg_speed_str=$(format_speed "$avg_speed_val")
    fi

    local file_count_str=""
    if [ -n "$PROGRESS_FILE_COUNT" ] && [ "$PROGRESS_FILE_COUNT" != "0" ]; then
        local files_moved=$((PROGRESS_FILE_COUNT - ${PROGRESS_REMAIN_FILES:-0}))
        file_count_str="${files_moved} files"
    fi

    # Build Discord completion message
    local discord_msg="${DISCORD_COMPLETION_MESSAGE:-$COMPLETION_MESSAGE}"
    discord_msg="${discord_msg//\{total_moved\}/$total_moved_str}"
    discord_msg="${discord_msg//\{file_count\}/$file_count_str}"
    discord_msg="${discord_msg//\{duration\}/$duration_str}"
    discord_msg="${discord_msg//\{avg_speed\}/$avg_speed_str}"
    COMPLETION_SUMMARY_DISCORD="$discord_msg"

    # Build Telegram completion message
    local telegram_msg="${TELEGRAM_COMPLETION_MESSAGE:-$COMPLETION_MESSAGE}"
    telegram_msg="${telegram_msg//\{total_moved\}/$total_moved_str}"
    telegram_msg="${telegram_msg//\{file_count\}/$file_count_str}"
    telegram_msg="${telegram_msg//\{duration\}/$duration_str}"
    telegram_msg="${telegram_msg//\{avg_speed\}/$avg_speed_str}"
    COMPLETION_SUMMARY_TELEGRAM="$telegram_msg"
}

# Function to convert bytes to human-readable format
human_readable() {
    local bytes=$1
    local tb gb kb mb
    if [ "$bytes" -ge 1099511627776 ]; then
        tb=$((bytes / 1099511627776))
        local tb_tenths=$(( (bytes * 10 / 1099511627776) % 10 ))
        local total_gb=$((bytes / 1073741824))
        echo "${tb}.${tb_tenths} TB (${total_gb} GB)"
    elif [ "$bytes" -ge 1073741824 ]; then
        gb=$((bytes / 1073741824))
        echo "${gb} GB"
    elif [ "$bytes" -ge 1048576 ]; then
        mb=$((bytes / 1048576))
        echo "${mb} MB"
    elif [ "$bytes" -ge 1024 ]; then
        kb=$((bytes / 1024))
        echo "${kb} KB"
    else
        echo "${bytes} Bytes"
    fi
}

# Calculate Estimated Time of Completion
calculate_etc() {
    local percent=$1
    local platform=$2
    local current_time
    current_time=$(date +%s)
    local elapsed=$((current_time - start_time))

    if [ "$percent" -gt 1 ] && [ "$elapsed" -ge 60 ] && [ "$PROGRESS_MOVED_BYTES" -gt 0 ]; then
        local rate=$((PROGRESS_MOVED_BYTES / elapsed))
        local remaining_time=0
        if [ "$rate" -gt 0 ]; then
            remaining_time=$((PROGRESS_REMAINING_BYTES / rate))
        fi
        if [ "$remaining_time" -lt 0 ]; then
            remaining_time=0
        fi
        local completion_time_estimate=$((current_time + remaining_time))

        if [[ $platform == "discord" ]]; then
            echo "<t:${completion_time_estimate}:R>"
        elif [[ $platform == "telegram" ]]; then
            date -d "@${completion_time_estimate}" +"%H:%M on %b %d (%Z)"
        fi
    else
        echo "Calculating..."
    fi
}

send_notification() {
    local percent=$1
    local remaining_data=$2
    local datetime
    datetime=$(date +"%B %d (%Y) - %H:%M:%S")
    local etc_discord
    etc_discord=$(calculate_etc "$percent" "discord")
    local etc_telegram
    etc_telegram=$(calculate_etc "$percent" "telegram")

    # Prepare file info placeholders
    local file_count_str=""
    local current_file_str=""
    if $ENABLE_FILE_INFO && [ -n "$PROGRESS_FILE_COUNT" ] && [ "$PROGRESS_FILE_COUNT" != "0" ]; then
        local files_moved=$((PROGRESS_FILE_COUNT - ${PROGRESS_REMAIN_FILES:-0}))
        file_count_str="${files_moved}/${PROGRESS_FILE_COUNT} files"
        if [ -n "$PROGRESS_CURRENT_FILE" ]; then
            current_file_str="$PROGRESS_CURRENT_FILE"
        fi
    fi

    # Prepare the messages using the predefined templates
    local value_message_discord="${DISCORD_MOVING_MESSAGE//\{percent\}/$percent}"
    value_message_discord="${value_message_discord//\{remaining_data\}/$remaining_data}"
    value_message_discord="${value_message_discord//\{etc\}/$etc_discord}"
    value_message_discord="${value_message_discord//\{file_count\}/$file_count_str}"
    value_message_discord="${value_message_discord//\{current_file\}/$current_file_str}"

    local value_message_telegram="${TELEGRAM_MOVING_MESSAGE//\{percent\}/$percent}"
    value_message_telegram="${value_message_telegram//\{remaining_data\}/$remaining_data}"
    value_message_telegram="${value_message_telegram//\{etc\}/$etc_telegram}"
    value_message_telegram="${value_message_telegram//\{file_count\}/$file_count_str}"
    value_message_telegram="${value_message_telegram//\{current_file\}/$current_file_str}"

    local footer_text="Version: v${CURRENT_VERSION}"
    if [[ -n "${LATEST_VERSION}" && "${LATEST_VERSION}" != "${CURRENT_VERSION}" ]]; then
        footer_text+=" (update available)"
    fi
    value_message_telegram+="&#10;&#10;${footer_text}"

    # Determine the color based on completion and percentage
    local color
    if [ "$percent" -ge 100 ] || ! is_mover_running; then
        build_completion_summary
        value_message_discord="$COMPLETION_SUMMARY_DISCORD"
        value_message_telegram="$COMPLETION_SUMMARY_TELEGRAM"
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
        local json_payload
        json_payload=$(jq -n \
                        --arg chat_id "$TELEGRAM_CHAT_ID" \
                        --arg text "$value_message_telegram" \
                        '{chat_id: $chat_id, text: $text, disable_notification: "false", parse_mode: "HTML"}')
        if $ENABLE_DEBUG; then
            log "Preparing to send to Telegram: $json_payload"
        fi
        local response
        response=$(curl -s -H "Content-Type: application/json" -X POST -d "$json_payload" "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage")
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
        local response
        response=$(curl -s -H "Content-Type: application/json" -X POST -d "$notification_data" "$DISCORD_WEBHOOK_URL" -w "\nHTTP status: %{http_code}\nCurl Error: %{errormsg}")
        if $ENABLE_DEBUG; then
            log "Discord response: $response"
        fi
    fi
}

# Initialize state directory for crash recovery
init_state_dir

# Main Script Execution Loop
while true; do
    log "Monitoring new mover process..."

    # Wait for the mover process to start
    log "Mover process not found, waiting to start monitoring..."
    while ! is_mover_running; do
        sleep 10
    done

    log "Mover process found, starting monitoring..."

    # Detect data source (mover.ini vs du polling)
    detect_data_source

    # Get mover PID for state tracking
    mover_pid=$(get_mover_pid) || mover_pid=""
    mover_start_time=$(get_mover_start_time "$mover_pid") || mover_start_time=""

    # Try to resume from saved state (crash recovery)
    if load_state; then
        log "Resuming monitoring from saved state — skipping 0% notification"
        # Get fresh progress data
        get_progress
        remaining_readable=$(human_readable "$PROGRESS_REMAINING_BYTES")
        percent="$PROGRESS_PERCENT"
    else
        # Fresh start — determine initial size
        if [ "$DATA_SOURCE" = "mover_ini" ]; then
            get_progress
            initial_size="$PROGRESS_TOTAL_BYTES"
        else
            initial_size=$(du -sb "${exclusion_params[@]}" "$CACHE_PATH" | cut -f1)
        fi

        initial_readable=$(human_readable "$initial_size")
        log "Initial total size of data: $initial_readable"

        start_time=$(date +%s)
        log "Monitoring started at: $(date -d "@$start_time" '+%Y-%m-%d %H:%M:%S')"

        # Check for late-join (mover already running before script started)
        if [ "$DATA_SOURCE" = "mover_ini" ] && [ "$PROGRESS_MOVED_BYTES" -gt 0 ]; then
            log "Late join detected — mover already $(( PROGRESS_PERCENT ))% complete (using mover.ini data)"
            percent="$PROGRESS_PERCENT"
            remaining_readable=$(human_readable "$PROGRESS_REMAINING_BYTES")
        elif [ "$DATA_SOURCE" = "du_polling" ] && [ -n "$mover_start_time" ]; then
            script_time=$(date +%s)
            if [ $((script_time - mover_start_time)) -gt 60 ]; then
                log "Late join detected — progress relative to cache size at script start"
            fi
            percent=0
            remaining_readable="$initial_readable"
        else
            percent=0
            remaining_readable="$initial_readable"
        fi

        LAST_NOTIFIED=-1
        send_notification "$percent" "$initial_readable"
        log "Initial notification sent with ${percent}% completion."
    fi

    # Monitor the progress
    last_du_time=0
    while true; do
        current_time=$(date +%s)

        # Only recalculate progress when DU_POLL_INTERVAL has passed
        if [ $((current_time - last_du_time)) -ge "$DU_POLL_INTERVAL" ]; then
            get_progress
            remaining_readable=$(human_readable "$PROGRESS_REMAINING_BYTES")
            percent="$PROGRESS_PERCENT"
            last_du_time=$current_time

            # Save state for crash recovery
            save_state

            if $ENABLE_DEBUG; then
                log "Progress poll [${DATA_SOURCE}]: percent=$percent, moved=${PROGRESS_MOVED_BYTES}, remaining=${PROGRESS_REMAINING_BYTES}, total=${PROGRESS_TOTAL_BYTES}"
                if [ -n "$PROGRESS_FILE_COUNT" ] && [ "$PROGRESS_FILE_COUNT" != "0" ]; then
                    log "  Files: ${PROGRESS_REMAIN_FILES}/${PROGRESS_FILE_COUNT} remaining"
                fi
            fi
        fi

        # Check if the mover process is still running
        if ! is_mover_running; then
            log "Mover process is no longer running."

            # Final progress read — captures mover.ini final state before it goes stale
            get_progress
            remaining_readable=$(human_readable "$PROGRESS_REMAINING_BYTES")

            log "Total data moved: ${PROGRESS_MOVED_BYTES} bytes, Total: ${PROGRESS_TOTAL_BYTES} bytes."
            send_notification 100 "$remaining_readable"
            save_last_run
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

        sleep 5  # Check every 5 seconds; progress only recalculated per DU_POLL_INTERVAL
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
