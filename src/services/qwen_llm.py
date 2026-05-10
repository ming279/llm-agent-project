import os
from typing import List, Optional, Any, Dict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.language_models import BaseChatModel
from pydantic import Field
import dashscope
from dashscope import Generation


class QwenChatModel(BaseChatModel):
    model: str = Field(default="qwen-turbo")
    temperature: float = Field(default=0.7)
    top_p: float = Field(default=0.8)
    max_tokens: int = Field(default=2000)
    api_key: Optional[str] = Field(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        if self.api_key is None:
            self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        dashscope.api_key = self.api_key

    @property
    def _llm_type(self) -> str:
        return "qwen"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        dashscope_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                dashscope_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                dashscope_messages.append({"role": "system", "content": msg.content})
            else:
                dashscope_messages.append({"role": "assistant", "content": msg.content})

        try:
            response = Generation.call(
                model=Generation.Models.qwen_turbo,
                messages=dashscope_messages,
                temperature=self.temperature,
                top_p=self.top_p,
                result_format="message",
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                chat_generation = ChatGeneration(
                    message=HumanMessage(content=content)
                )
                return ChatResult(generations=[chat_generation])
            else:
                raise Exception(f"API error: {response.message}")
        except Exception as e:
            raise e

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, **kwargs)


def get_qwen_model(
    model: str = "qwen-turbo",
    temperature: float = 0.7,
    max_tokens: int = 2000
) -> QwenChatModel:
    return QwenChatModel(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )


_llm_instance = None


def get_llm_service():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_qwen_model(temperature=0.7)
    return _llm_instance


llm_service = get_llm_service()