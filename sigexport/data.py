import json
import os
import sqlite3
from pathlib import Path
from typing import Tuple

from pysqlcipher3 import dbapi2 as sqlcipher
from typer import secho

from .models import Convos, Contacts


def fetch_data(
    db_file: Path,
    key: str,
    manual: bool = False,
    chats: str = None,
    include_empty: bool = False,
    log: bool = False,
) -> Tuple[Convos, Contacts]:
    """Load SQLite data into dicts."""

    contacts: Contacts = {}
    convos: Convos = {}
    if chats:
        chats_list = chats.split(",")

    db_file_decrypted = db_file.parents[0] / "db-decrypt.sqlite"
    if manual:
        if log:
            secho(f"Manually decrypting db to {db_file_decrypted}")
        if db_file_decrypted.exists():
            db_file_decrypted.unlink()
        command = (
            f'echo "'
            f"PRAGMA key = \\\"x'{key}'\\\";"
            f"ATTACH DATABASE '{db_file_decrypted}' AS plaintext KEY '';"
            f"SELECT sqlcipher_export('plaintext');"
            f"DETACH DATABASE plaintext;"
            f'" | sqlcipher {db_file}'
        )
        os.system(command)
        # use sqlite instead of sqlcipher as DB already decrypted
        db = sqlite3.connect(str(db_file_decrypted))
        c = db.cursor()
    else:
        db = sqlcipher.connect(str(db_file))
        c = db.cursor()
        # param binding doesn't work for pragmas, so use a direct string concat
        c.execute(f"PRAGMA KEY = \"x'{key}'\"")
        c.execute("PRAGMA cipher_page_size = 4096")
        c.execute("PRAGMA kdf_iter = 64000")
        c.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
        c.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

    query = "SELECT type, id, e164, name, profileName, members FROM conversations"
    c.execute(query)
    for result in c:
        if log:
            secho(f"\tLoading SQL results for: {result[3]}, aka {result[4]}")
        is_group = result[0] == "group"
        cid = result[1]
        contacts[cid] = {
            "id": cid,
            "name": result[3],
            "number": result[2],
            "profileName": result[4],
            "is_group": is_group,
        }
        if contacts[cid]["name"] is None:
            contacts[cid]["name"] = contacts[cid]["profileName"]

        if not chats or (result[3] in chats_list or result[4] in chats_list):
            convos[cid] = []

    c.execute("SELECT json, conversationId FROM messages ORDER BY sent_at")
    for result in c:
        content = json.loads(result[0])
        cid = result[1]
        if cid and cid in convos:
            convos[cid].append(content)

    if db_file_decrypted.exists():
        db_file_decrypted.unlink()

    if not include_empty:
        convos = {key: val for key, val in convos.items() if len(val) > 0}

    return convos, contacts
