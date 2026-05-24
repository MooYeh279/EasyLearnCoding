import httpx
from openai import OpenAI, AsyncOpenAI
from llm.base import LLMProvider
from config import AI_HTTP_TIMEOUT, AI_HTTP_CONNECT_TIMEOUT


_httpx_timeout = httpx.Timeout(connect=AI_HTTP_CONNECT_TIMEOUT, read=AI_HTTP_TIMEOUT, write=60.0, pool=10.0)


class OpenAILikeProvider(LLMProvider):
    """Provider for OpenAI-compatible APIs (OpenAI, DeepSeek, vLLM, etc.).

    Creates a fresh AsyncOpenAI client per async call to avoid event-loop
    binding issues — the background content-generation thread runs its own
    asyncio event loop via asyncio.run(), separate from uvicorn's main loop.
    """

    def __init__(self, api_key: str, base_url: str, timeout: httpx.Timeout = _httpx_timeout):
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def chat_completion(self, model: str, messages: list[dict], **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=model, messages=messages, **kwargs,
        )
        return response.choices[0].message.content

    async def chat_completion_async(self, model: str, messages: list[dict], **kwargs) -> str:
        async with AsyncOpenAI(
            api_key=self._api_key, base_url=self._base_url, timeout=self._timeout,
        ) as client:
            response = await client.chat.completions.create(
                model=model, messages=messages, **kwargs,
            )
            return response.choices[0].message.content

    async def chat_completion_stream_async(self, model: str, messages: list[dict], **kwargs):
        kwargs.pop("stream", None)
        async with AsyncOpenAI(
            api_key=self._api_key, base_url=self._base_url, timeout=self._timeout,
        ) as client:
            stream = await client.chat.completions.create(
                model=model, messages=messages, stream=True, **kwargs,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
