"""Optional, local-only installed Explorer gateway; frontend is built separately."""

import argparse
from importlib.util import find_spec
from typing import Any


def create_app() -> Any:
    for name in ("fastapi", "uvicorn", "httpx"):
        if find_spec(name) is None:
            raise ImportError("Explorer requires soma-neuro[explorer]")
    from services.explorer_api.app import create_app as factory

    return factory()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local Soma Explorer API; synthetic demo is default"
    )
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be in [1024, 65535]")
    app = create_app()
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
