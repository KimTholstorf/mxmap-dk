import asyncio
import sys
from pathlib import Path


def preprocess() -> None:
    from mail_sovereignty.preprocess import run

    # Optional country filter: `uv run preprocess IT IE NL`
    countries = [a.upper() for a in sys.argv[1:]] or None
    asyncio.run(run(Path("data.json"), countries=countries))


def postprocess() -> None:
    from mail_sovereignty.postprocess import run

    asyncio.run(run(Path("data.json")))


def validate() -> None:
    from mail_sovereignty.validate import run

    run(Path("data.json"), Path("."), quality_gate=True)
