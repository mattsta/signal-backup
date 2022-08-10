import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import emoji
import markdown
from bs4 import BeautifulSoup
from pysqlcipher3 import dbapi2 as sqlcipher
from typer import Argument, Option, colors, run, secho

log = False

Convo = Dict[str, Any]
Convos = Dict[str, List[Convo]]
Contact = Dict[str, str]
Contacts = Dict[str, Contact]


def source_location() -> Path:
    """Get OS-dependent source location."""

    home = Path.home()
    if sys.platform == "linux" or sys.platform == "linux2":
        source_path = home / ".config/Signal"
    elif sys.platform == "darwin":
        source_path = home / "Library/Application Support/Signal"
    elif sys.platform == "win32":
        source_path = home / "AppData/Roaming/Signal"
    else:
        secho("Please manually enter Signal location using --source.")
        sys.exit(1)

    return source_path


def copy_attachments(src: Path, dest: Path, convos: Convos, contacts: Contacts) -> None:
    """Copy attachments and reorganise in destination directory."""

    src_att = Path(src) / "attachments.noindex"
    dest = Path(dest)

    for key, messages in convos.items():
        name = contacts[key]["name"]
        if log:
            secho(f"\tCopying attachments for: {name}")
        # some contact names are None
        if name is None:
            name = "None"
        contact_path = dest / name / "media"
        contact_path.mkdir(exist_ok=True, parents=True)
        for msg in messages:
            if "attachments" in msg and msg["attachments"]:
                attachments = msg["attachments"]
                date = (
                    datetime.fromtimestamp(msg["timestamp"] / 1000.0)
                    .isoformat(timespec="milliseconds")
                    .replace(":", "-")
                )
                for i, att in enumerate(attachments):
                    try:
                        # Account for no fileName key
                        file_name = (
                            str(att["fileName"]) if "fileName" in att else "None"
                        )
                        # Sometimes the key is there but it is None, needs extension
                        if "." not in file_name:
                            content_type = att["contentType"].split("/")
                            try:
                                ext = content_type[1]
                            except IndexError:
                                ext = content_type[0]
                            file_name += "." + ext
                        att["fileName"] = (
                            f"{date}_{i:02}_{file_name}".replace(" ", "_")
                            .replace("/", "-")
                            .replace(",", "")
                            .replace(":", "-")
                        )
                        # account for erroneous backslash in path
                        att_path = str(att["path"]).replace("\\", "/")
                        shutil.copy2(src_att / att_path, contact_path / att["fileName"])
                    except KeyError:
                        if log:
                            p = att["path"] if "path" in att else ""
                            secho(f"\t\tBroken attachment:\t{name}\t{p}")
                    except FileNotFoundError:
                        if log:
                            p = att["path"] if "path" in att else ""
                            secho(f"\t\tAttachment not found:\t{name}\t{p}")
            else:
                msg["attachments"] = []


def timestamp_format(ts: float) -> str:
    return datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d %H:%M")


def make_simple(
    dest: Path, convos: Convos, contacts: Contacts, add_quote: bool = False
) -> None:
    """Output each conversation into a simple text file."""

    dest = Path(dest)
    for key, messages in convos.items():
        name = contacts[key]["name"]
        if log:
            secho(f"\tDoing markdown for: {name}")
        is_group = contacts[key]["is_group"]
        # some contact names are None
        if name is None:
            name = "None"
        mdpath = dest / name / "index.md"
        with open(mdpath, "w") as _:
            pass  # overwrite file if it exists
        mdfile = open(mdpath, "a")

        for msg in messages:
            try:
                date = timestamp_format(msg["sent_at"])
            except (KeyError, TypeError):
                try:
                    date = timestamp_format(msg["sent_at"])
                except (KeyError, TypeError):
                    date = "1970-01-01 00:00"
                    if log:
                        secho("\t\tNo timestamp or sent_at; date set to 1970")

            if log:
                secho(f"\t\tDoing {name}, msg: {date}")

            try:
                if msg["type"] == "call-history":
                    body = (
                        "Incoming call"
                        if msg["callHistoryDetails"]["wasIncoming"]
                        else "Outgoing call"
                    )
                else:
                    body = msg["body"]
            except KeyError:
                if log:
                    secho(f"\t\tNo body:\t\t{date}")
                body = ""
            if body is None:
                body = ""
            body = body.replace("`", "")  # stop md code sections forming
            body += "  "  # so that markdown newlines

            sender = "No-Sender"
            if "type" in msg.keys() and msg["type"] == "outgoing":
                sender = "Me"
            else:
                try:
                    if is_group:
                        for c in contacts.values():
                            num = c["number"]
                            if num is not None and num == msg["source"]:
                                sender = c["name"]
                    else:
                        sender = contacts[msg["conversationId"]]["name"]
                except KeyError:
                    if log:
                        secho(f"\t\tNo sender:\t\t{date}")

            for att in msg["attachments"]:
                file_name = att["fileName"]
                path = Path("media") / file_name
                path = Path(str(path).replace(" ", "%20"))
                if path.suffix and path.suffix.split(".")[1] in [
                    "png",
                    "jpg",
                    "jpeg",
                    "gif",
                    "tif",
                    "tiff",
                ]:
                    body += "!"
                body += f"[{file_name}](./{path})  "

            if "reactions" in msg and msg["reactions"]:
                reactions = []
                for r in msg["reactions"]:
                    try:
                        reactions.append(
                            f"{contacts[r['fromId']]['name']}: {r['emoji']}"
                        )
                    except KeyError:
                        if log:
                            secho(
                                f"\t\tReaction fromId not found in contacts: "
                                f"[{date}] {sender}: {r}"
                            )
                body += "\n(- " + ", ".join(reactions) + " -)"

            if "sticker" in msg and msg["sticker"]:
                try:
                    body = msg["sticker"]["data"]["emoji"]
                except KeyError:
                    pass

            quote = ""
            if add_quote:
                try:
                    quote = msg["quote"]["text"]
                    quote = f"\n>\n> {quote}\n>\n"
                except (KeyError, TypeError):
                    pass

            print(f"[{date}] {sender}: {quote}{body}", file=mdfile)


def fetch_data(
    db_file: Path,
    key: str,
    manual: bool = False,
    chats: str = None,
    include_empty=False,
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
        c2 = db.cursor()
    else:
        db = sqlcipher.connect(str(db_file))
        c = db.cursor()
        c2 = db.cursor()
        # param binding doesn't work for pragmas, so use a direct string concat
        for cursor in [c, c2]:
            cursor.execute(f"PRAGMA KEY = \"x'{key}'\"")
            cursor.execute("PRAGMA cipher_page_size = 4096")
            cursor.execute("PRAGMA kdf_iter = 64000")
            cursor.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA512")
            cursor.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512")

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

    c.execute("SELECT json, conversationId " "FROM messages " "ORDER BY sent_at")
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


def fix_names(contacts: Contacts) -> Contacts:
    """Convert contact names to filesystem-friendly."""
    fixed_contact_names = set()
    for key, item in contacts.items():
        contact_name = item["number"] if item["name"] is None else item["name"]
        if contacts[key]["name"] is not None:
            contacts[key]["name"] = "".join(
                x for x in emoji.demojize(contact_name) if x.isalnum()
            )
            if contacts[key]["name"] == "":
                contacts[key]["name"] = "unnamed"
            fixed_contact_name = contacts[key]["name"]
            if fixed_contact_name in fixed_contact_names:
                name_differentiating_number = 2
                while (
                    fixed_contact_name + str(name_differentiating_number)
                ) in fixed_contact_names:
                    name_differentiating_number += 1
                fixed_contact_name += str(name_differentiating_number)
                contacts[key]["name"] = fixed_contact_name
            fixed_contact_names.add(fixed_contact_name)

    return contacts


def create_html(dest: Path, msgs_per_page: int = 100) -> None:
    root = Path(__file__).resolve().parents[0]
    video_template = (root / "video.html").read_text()
    audio_template = (root / "audio.html").read_text()
    figure_template = (root / "figure.html").read_text()
    css_source = root / "style.css"
    css_dest = dest / "style.css"
    if os.path.isfile(css_source):
        shutil.copy2(css_source, css_dest)
    else:
        secho(
            f"Stylesheet ({css_source}) not found."
            f"You might want to install one manually at {css_dest}."
        )

    md = markdown.Markdown()

    for sub in dest.iterdir():
        if sub.is_dir():
            name = sub.stem
            if log:
                secho(f"\tDoing html for {name}")
            path = sub / "index.md"
            # touch first
            open(path, "a")
            with path.open() as f:
                lines_raw = f.readlines()
            lines = lines_to_msgs(lines_raw)
            last_page = int(len(lines) / msgs_per_page)
            htfile = open(sub / "index.html", "w")
            print(
                "<!doctype html>"
                "<html lang='en'><head>"
                "<meta charset='utf-8'>"
                f"<title>{name}</title>"
                "<link rel=stylesheet href='../style.css'>"
                "</head>"
                "<body>"
                "<div class=first><a href=#pg0>FIRST</a></div>"
                f"<div class=last><a href=#pg{last_page}>LAST</a></div>",
                file=htfile,
            )

            page_num = 0
            for i, msg in enumerate(lines):
                if i % msgs_per_page == 0:
                    nav = ""
                    if i > 0:
                        nav += "</div>"
                    nav += f"<div class=page id=pg{page_num}>"
                    nav += "<nav>"
                    nav += "<div class=prev>"
                    if page_num != 0:
                        nav += f"<a href=#pg{page_num-1}>PREV</a>"
                    else:
                        nav += "PREV"
                    nav += "</div><div class=next>"
                    if page_num != last_page:
                        nav += f"<a href=#pg{page_num+1}>NEXT</a>"
                    else:
                        nav += "NEXT"
                    nav += "</div></nav>"
                    print(nav, file=htfile)
                    page_num += 1

                date, sender, body = msg
                sender = sender[1:-1]
                date, time = date[1:-1].replace(",", "").split(" ")

                # reactions
                p = re.compile(r"\(- (.*) -\)")
                m = p.search(body)
                reactions = m.groups()[0].replace(",", "") if m else ""
                body = p.sub("", body)

                # quote
                p = re.compile(r">\n> (.*)\n>", flags=re.DOTALL)
                m = p.search(body)
                if m:
                    quote = m.groups()[0]
                    quote = f"<div class=quote>{quote}</div>"
                else:
                    quote = ""
                body = p.sub("", body)

                try:
                    body = md.convert(body)
                except RecursionError:
                    if log:
                        secho(f"Maximum recursion on message {body}, not converted")

                # links
                p = re.compile(r"(https{0,1}://\S*)")
                template = r"<a href='\1' target='_blank'>\1</a> "
                body = re.sub(p, template, body)

                # images
                soup = BeautifulSoup(body, "html.parser")
                imgs = soup.find_all("img")
                for im in imgs:
                    if im.get("src"):
                        temp = BeautifulSoup(figure_template, "html.parser")
                        src = im["src"]
                        temp.figure.div.label.div.img["src"] = src
                        temp.figure.label.img["src"] = src

                        alt = im["alt"]
                        temp.figure.label["for"] = alt
                        temp.figure.label.img["alt"] = alt
                        temp.figure.input["id"] = alt
                        temp.figure.div.label["for"] = alt
                        temp.figure.div.label.div.img["alt"] = alt
                        im.replace_with(temp)

                # voice notes
                voices = soup.select("a")
                p = re.compile(r'a href=".*\.(m4a|aac)"')
                for v in voices:
                    if p.search(str(v)):
                        href = v["href"]
                        temp = BeautifulSoup(audio_template, "html.parser")
                        temp.audio.source["src"] = href
                        v.replace_with(temp)

                # videos
                videos = soup.select(r"a[href*=\.mp4]")
                for v in videos:
                    href = v["href"]
                    temp = BeautifulSoup(video_template, "html.parser")
                    temp.video.source["src"] = href
                    v.replace_with(temp)

                cl = "msg me" if sender == "Me" else "msg"
                print(
                    f"<div class='{cl}'><span class=date>{date}</span>"
                    f"<span class=time>{time}</span>"
                    f"<span class=sender>{sender}</span>"
                    f"{quote}"
                    f"<span class=body>{soup.prettify()}</span>"
                    f"<span class=reaction>{reactions}</span>"
                    "</div>",
                    file=htfile,
                )
            print("</div>", file=htfile)
            print(
                "<script>if (!document.location.hash){"
                "document.location.hash = 'pg0';}</script>",
                file=htfile,
            )
            print("</body></html>", file=htfile)


def lines_to_msgs(lines: List[str]) -> List[List[str]]:
    p = re.compile(r"^(\[\d{4}-\d{2}-\d{2},{0,1} \d{2}:\d{2}\])(.*?:)(.*\n)")
    msgs = []
    for li in lines:
        m = p.match(li)
        if m:
            msgs.append(list(m.groups()))
        else:
            msgs[-1][-1] += li
    return msgs


def merge_attachments(media_new: Path, media_old: Path) -> None:
    for f in media_old.iterdir():
        if f.is_file():
            shutil.copy2(f, media_new)


def merge_chat(path_new: Path, path_old: Path) -> None:
    with path_old.open() as f:
        old_raw = f.readlines()
    with path_new.open() as f:
        new_raw = f.readlines()

    try:
        a = old_raw[0][:30]
        b = old_raw[-1][:30]
        c = new_raw[0][:30]
        d = new_raw[-1][:30]
        if log:
            secho(f"\t\tFirst line old:\t{a}")
            secho(f"\t\tLast line old:\t{b}")
            secho(f"\t\tFirst line new:\t{c}")
            secho(f"\t\tLast line new:\t{d}")
    except IndexError:
        if log:
            secho("\t\tNo new messages for this conversation")
        return

    old = lines_to_msgs(old_raw)
    new = lines_to_msgs(new_raw)

    merged = list(dict.fromkeys([m[0] + m[1] + m[2] for m in old + new]))

    with path_new.open("w") as f:
        f.writelines(merged)


def merge_with_old(dest: Path, old: Path) -> None:
    for dir_old in old.iterdir():
        if dir_old.is_dir():
            name = dir_old.stem
            if log:
                secho(f"\tMerging {name}")
            dir_new = old / name
            if dir_new.is_dir():
                merge_attachments(dir_new / "media", dir_old / "media")
                path_new = dir_new / "index.md"
                path_old = dir_old / "index.md"
                try:
                    merge_chat(path_new, path_old)
                except FileNotFoundError:
                    if log:
                        secho(f"\tNo old for {name}")
                secho()
            else:
                shutil.copytree(dir_old, dir_new)


def main(
    dest: Path = Argument(...),
    source: Optional[Path] = Option(None, help="Path to Signal source database"),
    old: Optional[Path] = Option(None, help="Path to previous export to merge"),
    overwrite: bool = Option(
        False, "--overwrite", "-o", help="Overwrite existing output"
    ),
    quote: bool = Option(True, "--quote/--no-quote", "-q", help="Include quote text"),
    paginate: int = Option(
        100, "--paginate", "-p", help="Messages per page in HTML; set to 0 for infinite"
    ),
    chats: str = Option(
        None, help="Comma-separated chat names to include: contact names or group names"
    ),
    html: bool = Option(True, help="Whether to create HTML output"),
    list_chats: bool = Option(
        False, "--list-chats", "-l", help="List available chats and exit"
    ),
    include_empty: bool = Option(
        False, "--include-empty", help="Whether to include empty chats"
    ),
    manual: bool = Option(
        False, "--manual", "-m", help="Attempt to manually decrypt DB"
    ),
    verbose: bool = Option(False, "--verbose", "-v"),
):
    """
    Read the Signal directory and output attachments and chat files to DEST directory.
    Assumes the following default directories, can be overridden wtih --source.

    \b
    Default Signal directories:
     - Linux: ~/.config/Signal
     - macOS: ~/Library/Application Support/Signal
     - Windows: ~/AppData/Roaming/Signal
    """

    global log
    log = verbose

    if source:
        src = Path(source)
    else:
        src = source_location()
    source = src / "config.json"
    db_file = src / "sql" / "db.sqlite"

    # Read sqlcipher key from Signal config file
    if source.is_file():
        with open(source, "r") as conf:
            key = json.loads(conf.read())["key"]
    else:
        secho(f"Error: {source} not found in directory {src}")
        sys.exit(1)

    if log:
        secho(f"Fetching data from {db_file}\n")
    convos, contacts = fetch_data(
        db_file, key, manual=manual, chats=chats, include_empty=include_empty
    )

    if list_chats:
        names = sorted(v["name"] for v in contacts.values() if v["name"] is not None)
        secho("\n".join(names))
        sys.exit()

    dest = Path(dest).expanduser()
    if not dest.is_dir() or overwrite:
        dest.mkdir(parents=True, exist_ok=True)
    else:
        secho(
            f"Output folder '{dest}' already exists, didn't do anything!", fg=colors.RED
        )
        secho("Use --overwrite (or -o) to ignore existing directory.", fg=colors.RED)
        sys.exit(1)

    contacts = fix_names(contacts)
    secho("Copying and renaming attachments")
    copy_attachments(src, dest, convos, contacts)
    secho("Creating markdown files")
    make_simple(dest, convos, contacts, quote)
    if old:
        secho(f"Merging old at {old} into output directory")
        secho("No existing files will be deleted or overwritten!")
        merge_with_old(dest, Path(old))
    if html:
        secho("Creating HTML files")
        if paginate <= 0:
            paginate = int(1e20)
        create_html(dest, msgs_per_page=paginate)
    secho("Done!", fg=colors.GREEN)


def cli():
    run(main)


if __name__ == "__main__":
    cli()
