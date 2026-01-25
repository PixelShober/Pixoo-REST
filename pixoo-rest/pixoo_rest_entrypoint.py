from fastapi.responses import RedirectResponse
from pixoo_rest.app import app as pixoo_app


async def app(scope, receive, send):
    if scope.get("type") == "http":
        path = scope.get("path", "")
        if path in ("", "/"):
            response = RedirectResponse(url="docs")
            await response(scope, receive, send)
            return

    await pixoo_app(scope, receive, send)
