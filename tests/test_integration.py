from pathlib import Path


def test_integration():
    from sigexport.main import main

    root = Path(__file__).resolve().parents[0]
    dest = Path("/tmp/signal-test-output")
    source = root / "data"

    main(
        dest=dest,
        source=source,
        old=None,
        overwrite=True,
        quote=True,
        paginate=100,
        chats=None,
        html=True,
        list_chats=False,
        include_empty=False,
        manual=False,
        verbose=True,
    )
