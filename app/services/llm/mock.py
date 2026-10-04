class MockProvider:
    """Offline deterministic provider: the rule-based parser does the work."""

    name = "mock"

    async def complete(self, system: str, user: str) -> str:
        return ""
