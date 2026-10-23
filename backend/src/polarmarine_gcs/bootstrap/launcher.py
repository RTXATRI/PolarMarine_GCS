from __future__ import annotations

import threading
import webbrowser

import uvicorn

from .app import create_app
from .logging import configure_logging
from .settings import Settings


def main(*, open_browser: bool = False, settings: Settings | None = None) -> None:
    settings = settings or Settings()
    configure_logging(settings)
    if open_browser:
        url = f"http://{settings.host}:{settings.port}"
        browser_timer = threading.Timer(1.0, webbrowser.open, args=(url,))
        browser_timer.daemon = True
        browser_timer.start()
    uvicorn.run(
        create_app(settings=settings),
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=True,
        log_config=None,
    )


def windows_main() -> None:
    settings = Settings()
    main(open_browser=settings.open_browser_on_start, settings=settings)


if __name__ == "__main__":
    main()
