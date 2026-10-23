from typing import cast

from fastapi import Request

from polarmarine_gcs.bootstrap.container import Container


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)
