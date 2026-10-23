from __future__ import annotations

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SpaStaticFiles(StaticFiles):
    """Serve built assets and fall back to index.html for Vue history routes."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory=str(directory), html=True, check_dir=True, follow_symlink=False)

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or Path(path).suffix:
                raise
            return await super().get_response("index.html", scope)
