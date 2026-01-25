from fastapi.responses import RedirectResponse
from pixoo_rest.app import app as pixoo_app


def _root_path_from_headers(headers):
    for key in (
        "x-ingress-path",
        "x-forwarded-prefix",
        "x-forwarded-path",
        "x-script-name",
    ):
        value = headers.get(key)
        if not value:
            continue
        value = value.split(",")[0].strip().rstrip("/")
        if not value:
            continue
        if not value.startswith("/"):
            value = f"/{value}"
        return value
    return ""


async def app(scope, receive, send):
    if scope.get("type") == "http":
        headers = {
            key.decode("latin1").lower(): value.decode("latin1")
            for key, value in scope.get("headers", [])
        }
        root_path = _root_path_from_headers(headers)
        if root_path:
            scope = dict(scope)
            scope["root_path"] = root_path

        path = scope.get("path", "")
        if path.startswith("//"):
            scope = dict(scope)
            scope["path"] = f"/{path.lstrip('/')}"
            path = scope["path"]
        if path in ("", "/"):
            response = RedirectResponse(url="docs")
            await response(scope, receive, send)
            return

    await pixoo_app(scope, receive, send)
