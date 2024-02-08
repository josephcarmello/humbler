# humbler :smirk:
A simple python script that reads a Minecraft log file, waits for your friends(or your) death, and posts them to discord for all to enjoy.

## Setup

### Container Details
The humbler runs in conjunction to a minecraft server that is running via a `itzg/docker-minecraft-server` based container. 
Log format might be standardized for minecraft, but anything customized from this container might not match your setup. 
You may need to customize to your specific setup to get this working properly.

### Requirements.txt
Make sure you install the necessary modules:
```
pip install -r requirements.txt
```

### Discord Webhook URL
Make sure you setup a webhook URL for the discord channel you want to send messages to. 

### .env File
There is a sample.env file that needs some entries for the script to work. Copy it to .env and fill in the variables:
```
cp sample.env .env
```
## Startup
Once all those entries have proper values, start the app:

```
python3 humbler.py
```
### Using a process management tool like PM2
If you have nodejs and nm installed, you can use a utility called `pm2` to help manage your python processes. It will allow you to create err and out files and manage the script to restart if it uses too much memory, etc. 

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

## TODO

- Deal with whitelist.json not existing - some servers dont use those!
