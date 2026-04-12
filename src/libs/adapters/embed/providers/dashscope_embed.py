import requests
import json
from typing import List, Union, Any
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction
from ..base_embed import BaseEmbed

class DashscopeEmbed(BaseEmbed, EmbeddingFunction):
    """
    适配百炼原生协议并完美对接 ChromaDB 的向量模型类。
    """

    def __init__(self, api_key: str, model: str = "text-embedding-v4", timeout: int = 60):
        # 原生协议 URL
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_batch_size = 10

    # 必须提供 name 方法供 ChromaDB 校验
    def name(self) -> str:
        return f"dashscope_{self.model}"

    # --- ChromaDB 标准接口实现 ---

    def embed_query(self, input: Union[str, List[str]]) -> Embeddings:
        """用于检索。注意：必须返回 List[List[float]]"""
        return self.__call__(input)

    def embed_documents(self, input: Documents) -> Embeddings:
        """用于存入文档。"""
        return self.__call__(input)

    def __call__(self, input: Union[str, List[str]]) -> Embeddings:
        """
        核心向量化逻辑：自动处理单条/多条输入及分批。
        """
        # 1. 统一格式：确保 input 永远是 List[str]，避免 [[...]] 嵌套
        if isinstance(input, str):
            texts = [input]
        else:
            texts = input

        all_embeddings = []
        # 2. 按照百炼限制进行分批 (每批 10 条)
        for i in range(0, len(texts), self.max_batch_size):
            batch = texts[i : i + self.max_batch_size]
            # 过滤空内容并确保是字符串
            clean_batch = [str(t) for t in batch if t and str(t).strip()]
            if not clean_batch:
                continue
                
            embeddings = self._request_embeddings(clean_batch)
            all_embeddings.extend(embeddings)
            
        return all_embeddings

    def _request_embeddings(self, batch: List[str]) -> List[List[float]]:
        """发送单次分批请求（原生协议）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": {
                "texts": batch # 原生协议格式要求
            },
            "parameters": {
                "text_type": "query" # 检索建议用 query，导入建议用 document
            }
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"❌ 百炼 API 报错: {response.text}")
                
            response.raise_for_status()
            result = response.json()

            # 解析返回结果
            embeddings_data = result.get("output", {}).get("embeddings", [])
            # 必须按 text_index 排序以保证结果与输入文本一一对应
            sorted_data = sorted(embeddings_data, key=lambda x: x.get("text_index", 0))
            return [item["embedding"] for item in sorted_data]
            
        except Exception as e:
            raise Exception(f"Dashscope 请求失败: {e}")

    # --- 原有项目兼容性方法 ---

    def embed(self, text: str) -> List[float]:
        """供项目其他部分调用单条向量化"""
        res = self.__call__(text)
        return res[0] if res else []

    def get_dimensions(self) -> int:
        return 1024