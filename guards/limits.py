"""Request size limits.

Pydantic validates the message length, but only *after* the whole body has been read and parsed.
This middleware rejects oversized bodies earlier, so a huge request cannot burn memory/CPU.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# 2000 chars at up to 4 bytes each is 8 KB of text, plus JSON overhead. 16 KiB leaves margin
# while still being tiny compared to the platform's own multi-megabyte ceiling.
MAX_BODY_BYTES = 16 * 1024

_TOO_LARGE = json.dumps({"detail": "Request is too large."}).encode()


class BodySizeLimitMiddleware:
    """Reject requests whose body exceeds max_bytes, whether declared or streamed."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: the client declared a size that is already too big.
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                await self._reject(send)
                return

        # Slow path: no/lying Content-Length (e.g. chunked). Count bytes as they arrive.
        received = 0
        rejected = False

        async def counting_receive() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Answer 413 ourselves, then tell the app the client went away. (Raising here
                    # would be caught by the framework's body parsing and turned into a 400.)
                    rejected = True
                    await self._reject(send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not rejected:  # after we've answered 413, discard whatever the app tries to send
                await send(message)

        await self.app(scope, counting_receive, guarded_send)

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE})
