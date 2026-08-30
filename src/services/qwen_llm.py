import os
import time
from typing import List, Optional, Any, Dict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.language_models import BaseChatModel
from pydantic import Field
import dashscope
from dashscope import Generation


class QwenChatModel(BaseChatModel):
    model: str = Field(default="qwen-turbo-latest")
    temperature: float = Field(default=0.7)
    top_p: float = Field(default=0.8)
    max_tokens: int = Field(default=2000)
    api_key: Optional[str] = Field(default=None)
    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=2.0)

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

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = Generation.call(
                    model="qwen-turbo-latest",
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
                    last_error = Exception(f"API error: {response.message}")
                    
            except Exception as e:
                last_error = e
            
            # 如果是限流错误，增加重试延迟
            if "rate limit" in str(last_error).lower():
                delay = self.retry_delay * (attempt + 1) * 2
            else:
                delay = self.retry_delay * (attempt + 1)
            
            if attempt < self.max_retries - 1:
                time.sleep(delay)
        
        if last_error:
            error_msg = str(last_error)
            if "rate limit" in error_msg.lower():
                error_msg = f"API限流: {error_msg}，请稍后再试或联系管理员调整API配额"
            elif "API key" in error_msg.lower():
                error_msg = f"API密钥错误: {error_msg}，请检查环境变量DASHSCOPE_API_KEY"
            elif "unauthorized" in error_msg.lower():
                error_msg = f"认证失败: {error_msg}，请检查API密钥是否正确"
            raise Exception(error_msg)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, **kwargs)


def get_qwen_model(
    model: str = "qwen-turbo-latest",
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