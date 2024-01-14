# humbler :smirk:
A simple python script that reads a Minecraft log file, waits for death messages, and posts them to a discord webhook.

## Setup

### Requirements.txt
Make sure you install the necessary modules:
```
pip install -r requirements.txt
```

### Discord Webhook URL
Make sure you setup a webhook URL for the discord channel you want to send messages to. 

### .env File
There is a simple .env file that needs some entries for the script to work:
```
cp sample-.env .env
```
## Startup
Once all those entries have proper values, start the app:

```
python3 humbler.py
```
