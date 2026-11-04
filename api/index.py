"""Vercel entrypoint: the serverless demo API.

Vercel routes one function per file, so only `/api/index` reaches this app —
a suffix like `/api/index/analyze` is not routed at all. The frontend therefore
sends the logical endpoint as `?r=/analyze` (see `web/portal/review.js`), and
this shim restores it as the ASGI path before the FastAPI app sees it.

Local tests and the Docker demo hit the app at its own routes, so nothing here
affects them.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

from mock_fen_api.serverless import app as fen_app

PREFIX = "/api/index"


def _rewrite(scope: dict) -> dict:
    """Turn `?r=/analyze&x=1` into path `/analyze` with the rest of the query."""
    path = scope.get("path") or "/"
    if path.startswith(PREFIX):
        path = path[len(PREFIX):] or "/"

    query = scope.get("query_string") or b""
    pairs = parse_qsl(query.decode("latin-1"), keep_blank_values=True)
    routed = None
    rest = []
    for key, value in pairs:
        if key == "r" and routed is None:
            routed = value
        else:
            rest.append((key, value))

    if path == "/" and routed:
        path = routed if routed.startswith("/") else "/" + routed

    scope = dict(scope)
    scope["path"] = path
    scope["raw_path"] = path.encode("utf-8")
    scope["query_string"] = urlencode(rest).encode("latin-1")
    return scope


class Router:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope = _rewrite(scope)
        await self.app(scope, receive, send)


app = Router(fen_app)
