#!/usr/bin/env python

import json
import os
import sys
from pathlib import Path

import click
from pysqlcipher3 import dbapi2 as sqlcipher


@click.command()
@click.option("--from", "-f", "from_", type=click.Path(), help="Signal directory (on Linux: ~/.config/Signal/)")
@click.option("--to", "-t", type=click.Path(), help="Output directory for JSON and HTML")
def export(from_, to):
    # Locations of things
    path = Path(from_)
    CONFIG = path / "config.json"
    DB = path / "sql/db.sqlite"
    html_in = Path(os.path.dirname(os.path.abspath(__file__))) / "chattr.html"

    to = Path(to)
    to.mkdir(parents=True, exist_ok=True)
    cont = to / "contacts.json"
    conv = to / "conversations.json"
    html = to / "conversations.html"

    # Read sqlcipher key from Signal config file
    try:
        with open(CONFIG, "r") as conf:
            key = json.loads(conf.read())["key"]
    except FileNotFoundError:
        print(f"Error: {CONFIG} not found in current directory!")
        print("Run again from inside your Signal Desktop user directory")
        sys.exit(1)

    db = sqlcipher.connect(str(DB))
    c = db.cursor()
    c2 = db.cursor()

    # param binding doesn't work for pragmas, so use a direct string concat
    for cursor in [c, c2]:
        cursor.execute(f"PRAGMA KEY = \"x'{key}'\"")
        cursor.execute(f"PRAGMA cipher_page_size = 1024")
        cursor.execute(f"PRAGMA kdf_iter = 64000")
        cursor.execute(f"PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
        cursor.execute(f"PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1")

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
            "isGroup": isGroup,
        }
        convos[cId] = []

        if isGroup:
            usableMembers = []
            # Attempt to match group members from ID (phone number) back to real
            # names if the real names are also in your contact/conversation list.
            for member in result[5].split():
                c2.execute(
                    "SELECT name, profileName FROM conversations WHERE id=?", [member]
                )
                for name in c2:
                    useName = name[0] if name else member
                    usableMembers.append(useName)

            conversations[cId]["members"] = usableMembers

    # We either need an ORDER BY or a manual sort() below because our web interface
    # processes message history in array order with javascript object traversal.
    # If we skip ordering here, the web interface will show the message history in
    # a random order, which can be amusing but not necessarily very useful.
    c.execute(
        "SELECT json, conversationId, sent_at, received_at FROM messages ORDER BY sent_at"
    )
    messages = []
    for result in c:
        content = json.loads(result[0])
        cId = result[1]
        if not cId:
            # Signal's data model isn't as stable as one would imagine
            continue
        convos[cId].append(content)

    # Unnecessary with our ORDER BY clause
    if False:
        from operator import itemgetter

        for convo in convos:
            convos[convo].sort(key=itemgetter("sent_at"))

    # Exporting JSON to files is optional since we also paste it directly
    # into the resulting HTML interface
    with open(cont, "w") as con:
        json.dump(conversations, con)
        contactsJSON = json.dumps(conversations)

    with open(conv, "w") as ampc:
        json.dump(convos, ampc)
        convosJSON = json.dumps(convos)

    # Create end result of interactive HTML interface with embedded and formatted
    # chat history for all contacts/conversations.
    with open(html_in, "r") as chattr:
        newChat = chattr.read()
        updated = newChat.replace(
            "JSONINSERTHERE",
            f"var contacts = {contactsJSON}; var convos = {convosJSON};",
        )

        with open(html, "w") as mine:
            mine.write(updated)


if __name__ == "__main__":
    export()
