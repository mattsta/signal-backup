# Signal Conversation Archive Backup

## SCAB

Welcome to [Signal Conversation Archive Backup (SCAB)](https://github.com/mattsta/signal-backup)!

Full writeup is at: https://matt.sh/signal-backup

## Usage

To backup your Signal Desktop database, run the following commands to:

-   Check out SCAB
-   Install Python requirements
-   Copy your Signal Desktop database (and attachments) into a new directory so nothing is read against your live Signal DB
-   Generate a single local HTML page web viewer for all your conversations

`pysqlcipher3` now has to be compiled from source:

```sh
git clone https://github.com/rigglemania/pysqlcipher3.git
```

# Linux:

```sh
sudo apt-get install libsqlcipher-dev
```

# Mac:

```sh
brew install sqlcipher
```

```sh
python3 setup.py build
python3 setup.py install
```

```sh
git clone https://github.com/mattsta/signal-backup
cd signal-backup
pip3 install -r requirements.txt
rsync -avz "/Users/$(whoami)/Library/Application Support/Signal" Signal-Archive
cd Signal-Archive/Signal
python3 ../../scab.py
open myConversations.html
```
