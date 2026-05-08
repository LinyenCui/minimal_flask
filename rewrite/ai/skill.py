"""
Skill 定義（spec §6.2）— 按意圖分類載入「prompt + tool subset」

每個 skill 包：
  - name: 唯一識別
  - system_prompt: 給 LLM 的領域 prompt
  - tools: list[(callable, schema_dict)]
    callable 是 atomic tool 函數
    schema_dict 是 Gemini FunctionDeclaration 的 parameters JSON

設計考量：
  - tool callable 必須是 keyword-only args（rewrite atomic tools 都是）
  - schema_dict 跟 tool callable 鬆綁，方便 prompt-only schema 修改
  - get_tool(name) 給 Agent dispatch 用
"""
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from vertexai.generative_models import FunctionDeclaration


@dataclass
class Skill:
    name: str
    system_prompt: str
    tools: List[Tuple[Callable, dict]]  # [(fn, schema)]

    def function_declarations(self) -> List[FunctionDeclaration]:
        """產生 Gemini Tool 用的 FunctionDeclaration 清單"""
        return [
            FunctionDeclaration(
                name=fn.__name__,
                description=schema.get('description') or (fn.__doc__ or '').strip().split('\n')[0],
                parameters=schema['parameters'],
            )
            for fn, schema in self.tools
        ]

    def get_tool(self, name: str) -> Optional[Callable]:
        for fn, _ in self.tools:
            if fn.__name__ == name:
                return fn
        return None
