# Mover Status

<p align="center">
  <img src="https://i.imgur.com/51gQKps.png" alt="MoverStatus Script"/>
</p>


### Description
This Bash script is designed to monitor the progress of the UnraidOS Mover utility, which transfers data from SSD cache to HDD storage in an UnraidOS system. 

The script checks the status of the mover process and calculates the amount of data left to move. It then formats this information into a readable format, including the percentage of the task completed and an estimated time of completion. 

Notifications about the mover's progress are periodically sent to a Discord channel via a webhook. These notifications include detailed progress updates and an estimated completion time, helping users track the mover process effectively. The script supports customization for notification frequency and allows users to specify directory paths to exclude from the data transfer calculation.

This functionality is particularly useful for UnraidOS users who want real-time updates about their system’s data management tasks, delivered directly to their Discord server.

### How it works
1) When the script runs, it'll wait and look for the Unraid Mover script, before it'll start
2) When it has found the Unraid Mover script, it'll post the first message to your Discord webhook
3) It will try and calculate how much data is on your cache, **minus** the paths you choose to exclude (the time-estimation can be a bit off)
4) In my case, I'm excluding data in my Mover, that other apps are using, e.g. folders related to qBittorrent and/or SABnzbd, or hidden folders
5) It'll post a new message every 2 minutes by default, but this can be changed in the script
6) If the calculations are correct, it'll exit the script, when it has reached 100% data moved from Cache --> Array 
7) Otherwise, the script will automatically set itself to 100%, when it detects the UnraidOS Mover script is no longer running

### Installation
I'm using the UnraidOS plugin named "[User Scripts](https://forums.unraid.net/topic/48286-plugin-ca-user-scripts/)"
1) Go into "**Settings**"
2) Select "**User Scripts**"
3) Select "**Add New Script**"
4) Name your script "**Mover Status**" (or anything else)
5) Select/hover the **Settings Wheel** icon of the Mover Status script you just created
6) Select "**Edit Script**"
7) Copy everything from the [moverStatus.sh](https://raw.githubusercontent.com/engels74/mover-status/main/moverStatus.sh) into the file 
8) Edit the variables at the top to your liking (you don't **have** to define any excluded folders)
9) Select "**Save Changes**" to save the script
10) Schedule to run it a few minutes before your Mover is planned to start, use a [crontab generator](https://crontab.guru) for this


## Images (preview)
<img src="https://i.imgur.com/BXhTkfk.png" width="50%" alt="An example of how it looks">
