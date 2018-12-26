# Signal Conversation Archive Backup

## SCAB

Welcome to [Signal Conversation Archive Backup (SCAB)](https://github.com/mattsta/signal-backup)!

Full writeup is at: https://matt.sh/signal-backup

## Usage

To backup your Signal Desktop database, run the following commands to:

- check out SCAB
- install Python requirements
- copy your Signal Desktop database (and attachments) into a new directory so nothing is read against your live Signal DB
- generate a single local HTML page web viewer for all your conversations

```erlang
git clone https://github.com/mattsta/signal-backup
pip3 install -r requirements.txt
cd signal-backup
rsync -avz "/Users/$(whoami)/Library/Application Support/Signal" Signal-Archive
cd Signal-Archive
python3 ../scab.py
open myConversations.html
```
