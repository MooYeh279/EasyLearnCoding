class LLMProvider:
    """Abstract base for LLM providers. Extend to support non-OpenAI models."""

    def chat_completion(self, model: str, messages: list[dict], **kwargs) -> str:
        raise NotImplementedError

    async def chat_completion_async(self, model: str, messages: list[dict], **kwargs) -> str:
        raise NotImplementedError

    async def chat_completion_stream_async(self, model: str, messages: list[dict], **kwargs):
        """Stream chat completion, yielding text chunks."""
        raise NotImplementedError

    async def chat_completion_with_tools_async(self, model: str, messages: list[dict],
                                                tools: list[dict] | None = None, **kwargs) -> dict:
        """Return full response dict with optional tool_calls: {content, tool_calls}."""
        raise NotImplementedError
