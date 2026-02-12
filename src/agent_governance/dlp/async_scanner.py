from __future__ import annotations

import asyncio

from .scanner import DLPScanner


class AsyncDLPScanner:
    def __init__(self, scanner: DLPScanner) -> None:
        self.scanner = scanner

    async def scan_text(self, text: str):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.scanner.scan_text, text)
