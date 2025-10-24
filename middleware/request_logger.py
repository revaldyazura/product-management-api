import time
import uuid
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from utils.logging_config import request_id_ctx, user_id_ctx

logger = logging.getLogger("app.middleware.request")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token_req = request_id_ctx.set(request_id)
        token_usr = user_id_ctx.set("-")

        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            client = request.client.host if request.client else "-"
            path = request.url.path
            method = request.method
            status = locals().get("response").status_code if "response" in locals() else 500

            logger.info(f'{client} "{method} {path}" {status} {duration_ms}ms')

            if "response" in locals():
                response.headers["X-Request-ID"] = request_id

            request_id_ctx.reset(token_req)
            user_id_ctx.reset(token_usr)

        return response