"""`python -m atlas` arranca el servidor."""

import uvicorn

from atlas.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run("atlas.main:app", host=s.host, port=s.port, reload=False)


if __name__ == "__main__":
    main()
