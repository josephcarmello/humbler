
<p align="center" width="100%"><img width="20%" height="20%" src="https://github.com/josephcarmello/humbler/assets/14276892/2baf1a40-985b-4ea0-a966-8327ff2653a4" /></p>

# humbler :smirk:

A simple python script that reads a Minecraft log file, waits for your friends(or your) death, and posts them to discord for all to enjoy. The humbler will also track each user's total deaths in a local sqlite db.

Who will be the last member of the server to get humbled?!

<p align="center" width="100%"><img src="https://github.com/josephcarmello/humbler/assets/14276892/8a7bdf5f-e477-4d24-880c-a969a480cc2a" /></p>

## Setup

### Minimum versions
This was built with Python 3.11 and is being used with Minecraft 1.21 (Previous versions may work, but I won't be troubleshooting those!) 

### Container Details
The humbler was built and runs in conjunction to a minecraft server that is running via a `itzg/docker-minecraft-server` based container. 
Log format might be standardized for minecraft, but anything customized from this container might not match your setup. 
You may need to customize to your specific regex or deathmessages to get this working properly in a setup that differs from that.

### Requirements.txt
Make sure you install the necessary modules (As with all new apps, if you're not baking this into a docker container, setup a virtualenv using venv, uv, poetry, etc):
```
pip install -r requirements.txt
```

### Discord Webhook URL
You will need to setup a webhook URL for the Discord channel you want to send messages to.

Here is the official docs from Discord on how to do the: https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks

Keep that safe and don't share it with anyone!

### .env File
There is a `sample.env` file that needs some entries for the script to work. Copy it to `.env` and fill in the variables:
```
cp sample.env .env
```
## Startup
Once all those entries have proper values, start the app:

```
python3 humbler.py
```
### Using a process management tool like PM2
If you have nodejs and npm installed, you can use a utility called `pm2` to help manage your python processes. 
It will allow you to create .err and .out files and manage the script to restart if it uses too much memory, etc.
This will also daemonize it so that you can run it as a "process" instead of a user initiated session.

You can install pm2 with the following:
```npm install pm2 -g```

Once installed you will need to create an "ecosystem.json" file which will act as a configuration file for pm2 to know where your app lives and further details about it.

An example ecosystem file that will live in your pm2 process start directory:
```
module.exports = {
  apps : [{
    name: 'Humbler',
    script: '/data/scripts/humbler/humbler.py',
    interpreter: '/usr/bin/python3',
    autorestart: false,
    watch: true,
    pid: '/data/scripts/humbler/humbler.pid',
    out_file: "/data/scripts/humbler/humbler.out",
    error_file: "/data/scripts/humbler/humbler.err",
    instances: 1,
    max_memory_restart: '1G',
    env_production : {
      ENV: 'production'
    }
  }]
};
```
