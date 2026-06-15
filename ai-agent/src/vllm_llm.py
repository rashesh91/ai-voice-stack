import logging

from openai import AsyncOpenAI
from livekit.agents import llm
from livekit.agents.llm import ChatChunk, ChoiceDelta
from livekit.agents.types import APIConnectOptions

logger = logging.getLogger(__name__)


class VLLMChat(llm.LLM):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 80,
    ):
        super().__init__()
        self._client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        conn_options: APIConnectOptions = APIConnectOptions(),
        **kwargs,
    ) -> "VLLMStream":
        return VLLMStream(
            llm=self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )


class VLLMStream(llm.LLMStream):
    async def _run(self) -> None:
        messages = []
        for msg in self._chat_ctx.messages():
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            content = _extract_text(msg.content)
            if content:
                messages.append({"role": role, "content": content})

        stream = await self._llm._client.chat.completions.create(
            model=self._llm._model,
            messages=messages,
            temperature=self._llm._temperature,
            max_tokens=self._llm._max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta.content:
                continue
            self._event_ch.send_nowait(ChatChunk(
                id=chunk.id,
                delta=ChoiceDelta(role="assistant", content=delta.content),
            ))


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif hasattr(item, "text"):
                parts.append(item.text)
        return "".join(parts)
    return str(content) if content else ""
