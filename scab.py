#!/usr/bin/env python3.6

from pysqlcipher3 import dbapi2 as sqlcipher

import json
import os

# Locations of things
BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = "config.json"
DB = "sql/db.sqlite"

# Read sqlcipher key from Signal config file
try:
    with open(CONFIG, "r") as conf:
        key = json.loads(conf.read())['key']
except FileNotFoundError:
    print(f"Error: {CONFIG} not found in current directory!")
    print("Run again from inside your Signal Desktop user directory")
    import sys
    sys.exit(1)

db = sqlcipher.connect(DB)
c = db.cursor()
c2 = db.cursor()

# param binding doesn't work for pragmas, so use a direct string concat
for cursor in [c, c2]:
    cursor.execute(f'PRAGMA KEY = "x\'{key}\'"')

# Hold numeric user id to conversation/user names
conversations = {}

# Hold message body data
convos = {}

c.execute("SELECT json, id, name, profileName, type, members FROM conversations")
for result in c:
    cId = result[1]
    isGroup = result[4] == "group"
    conversations[cId] = {
        "id": result[1],
        "name": result[2],
        "profileName": result[3],
        "isGroup": isGroup}
    convos[cId] = []

    if isGroup:
        usableMembers = []
        # Attempt to match group members from ID (phone number) back to real
        # names if the real names are also in your contact/conversation list.
        for member in result[5].split():
            c2.execute(
                "SELECT name, profileName FROM conversations WHERE id=?",
                [member])
            for name in c2:
                useName = name[0] if name else member
                usableMembers.append(useName)

        conversations[cId]["members"] = usableMembers

# We either need an ORDER BY or a manual sort() below because our web interface
# processes message history in array order with javascript object traversal.
# If we skip ordering here, the web interface will show the message history in
# a random order, which can be amusing but not necessarily very useful.
c.execute(
    "SELECT json, conversationId, sent_at, received_at FROM messages ORDER BY sent_at")
messages = []
for result in c:
    content = json.loads(result[0])
    cId = result[1]
    convos[cId].append(content)

# Unnecessary with our ORDER BY clause
if False:
    from operator import itemgetter
    for convo in convos:
        convos[convo].sort(key=itemgetter("sent_at"))

# Exporting JSON to files is optional since we also paste it directly
# into the resulting HTML interface
with open("contacts.json", "w") as con:
    json.dump(conversations, con)
    contactsJSON = json.dumps(conversations)

with open("convos.json", "w") as ampc:
    json.dump(convos, ampc)
    convosJSON = json.dumps(convos)

# Create end result of interactive HTML interface with embedded and formatted
# chat history for all contacts/conversations.
with open(f"{BASE}/chattr.html", "r") as chattr:
    newChat = chattr.read()
    updated = newChat.replace(
        "JSONINSERTHERE",
        f"var contacts = {contactsJSON}; var convos = {convosJSON};")

    with open("myConversations.html", "w") as mine:
        mine.write(updated)
