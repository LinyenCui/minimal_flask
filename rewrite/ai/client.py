"""
LLMClient 抽象 + GeminiClient 實作（spec §6.1）

切換 Provider（Gemini → Claude）= 改一個依賴注入。

最小可運作版：
  - chat(messages, tools) → LLMResponse
  - LLMResponse 含 text 跟 tool_calls，caller 自行 dispatch tool

複用 main 的 init_vertexai（不重新做 service account 驗證），但其餘邏輯獨立。
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional

from google.genai import types

from modules.services.ai_service import get_genai_client, MODEL_ID

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class LLMResponse:
    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw: Any = None

    @property
    def has_tool_call(self) -> bool:
        return bool(self.tool_calls)


class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list, tools: Optional[list] = None) -> LLMResponse:
        """
        messages: list[{'role': 'system'|'user', 'content': str}]
        tools: list[FunctionDeclaration] | None
        """


class GeminiClient(LLMClient):
    """Gemini 2.5 Flash via Vertex AI"""

    def __init__(self, model_name: Optional[str] = None,
                 temperature: float = 0.2):
        self.client = get_genai_client()  # 重用共用 genai client（service account）
        self.model_name = model_name or MODEL_ID
        self.temperature = temperature

    def chat(self, messages: list, tools: Optional[list] = None) -> LLMResponse:
        gemini_tools = [types.Tool(function_declarations=tools)] if tools else None

        # Gemini chat 不分 system/user role，把 system 內容放最前面
        sys_parts = [m['content'] for m in messages if m.get('role') == 'system']
        user_parts = [m['content'] for m in messages if m.get('role') == 'user']
        full_prompt = '\n\n'.join(sys_parts + user_parts)

        logger.info(f"[GeminiClient] prompt {len(full_prompt)} chars, "
                    f"tools={len(tools) if tools else 0}")
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=0.8,
                max_output_tokens=2048,
                tools=gemini_tools,
            ),
        )

        return self._parse_response(response)

    @staticmethod
    def _parse_response(response) -> LLMResponse:
        text_parts: list = []
        tool_calls: List[ToolCall] = []

        if not response.candidates:
            logger.warning("[GeminiClient] no candidates in response")
            return LLMResponse(raw=response)

        content = response.candidates[0].content
        if not content or not content.parts:
            return LLMResponse(raw=response)
        for part in content.parts:
            # function call
            fc = getattr(part, 'function_call', None)
            if fc and fc.name:
                args = {k: v for k, v in fc.args.items()} if fc.args else {}
                tool_calls.append(ToolCall(name=fc.name, args=args))
                continue
            # text
            t = getattr(part, 'text', None)
            if t:
                text_parts.append(t)

        return LLMResponse(
            text=''.join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            raw=response,
        )
