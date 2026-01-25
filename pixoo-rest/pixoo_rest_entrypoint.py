from fastapi.responses import RedirectResponse
from pixoo_rest.app import app as pixoo_app


@pixoo_app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


app = pixoo_app
