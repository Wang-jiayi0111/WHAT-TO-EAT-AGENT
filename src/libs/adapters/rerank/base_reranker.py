from abc import ABC, abstractmethod
from typing import List

class BaseReranker(ABC):
    """重排器抽象基类"""
    @abstractmethod
    def rerank(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """
        对检索结果进行重新打分和排序
        """
        pass