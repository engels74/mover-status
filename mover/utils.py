# mover/utils.py
import math
from datetime import datetime, timedelta
from typing import Union

def human_readable_size(bytes_size: int) -> str:
    """
    Convert bytes to human-readable format.
    
    :param bytes_size: Size in bytes
    :return: Human-readable string representation of the size
    """
    if bytes_size == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(bytes_size, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_size / p, 2)
    return f"{s} {size_name[i]}"

def calculate_etc(percent: int, start_time: datetime, total_data_moved: int, current_size: int, platform: str) -> str:
    """
    Calculate Estimated Time of Completion.
    
    :param percent: Current completion percentage
    :param start_time: Start time of the mover process
    :param total_data_moved: Total data moved so far in bytes
    :param current_size: Current size of remaining data in bytes
    :param platform: 'discord' or 'telegram'
    :return: Formatted string of estimated completion time
    """
    if percent <= 0:
        return "Calculating..."
    
    current_time = datetime.now()
    elapsed = (current_time - start_time).total_seconds()
    estimated_total_time = elapsed * (total_data_moved + current_size) / total_data_moved
    remaining_time = estimated_total_time - elapsed
    completion_time_estimate = current_time + timedelta(seconds=remaining_time)
    
    if platform == "discord":
        return f"<t:{int(completion_time_estimate.timestamp())}:R>"
    elif platform == "telegram":
        return completion_time_estimate.strftime("%H:%M on %b %d (%Z)")
    else:
        return completion_time_estimate.isoformat()

def get_color_from_percent(percent: int) -> int:
    """
    Determine the color based on the completion percentage.
    
    :param percent: Completion percentage
    :return: Color code as an integer
    """
    if percent >= 100:
        return 65280  # Green
    elif percent <= 34:
        return 16744576  # Light Red
    elif percent <= 65:
        return 16753920  # Light Orange
    else:
        return 9498256  # Light Green

def is_version_newer(current_version: str, latest_version: str) -> bool:
    """
    Compare version strings to determine if the latest version is newer.
    
    :param current_version: Current version string
    :param latest_version: Latest version string
    :return: True if latest_version is newer, False otherwise
    """
    def parse_version(v):
        return tuple(map(int, v.split('.')))
    
    return parse_version(latest_version) > parse_version(current_version)
