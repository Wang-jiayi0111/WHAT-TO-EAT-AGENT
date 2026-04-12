"""
Module for splitting documents into smaller chunks.
"""
from typing import List, Optional
from dataclasses import dataclass
import re
import math
import logging
from src.ingestion.processors.loader import Document
from langchain.text_splitter import MarkdownHeaderTextSplitter

def flatten_metadata(metadata: dict):
    """
    Flatten nested metadata dictionaries to ensure compatibility with ChromaDB.
    ChromaDB only supports str, int, float, bool, list, and None as metadata values.
    """
    flattened = {}
    for key, value in metadata.items():
        if isinstance(value, dict):
            # Convert nested dictionary to string representation
            flattened[key] = str(value)
        elif isinstance(value, (list, tuple)):
            # Process lists/tuples - if they contain dicts, convert those to strings
            flattened_list = []
            for item in value:
                if isinstance(item, dict):
                    flattened_list.append(str(item))
                else:
                    flattened_list.append(item)
            flattened[key] = flattened_list
        else:
            # Keep primitive values as they are
            flattened[key] = value
    return flattened


@dataclass
class Chunk:
    """Represents a document chunk."""
    id: str
    content: str
    metadata: dict
    source_document_id: str
    chunk_index: int


class BaseSplitter:
    """Abstract base class for all splitters."""

    def split(self, documents: List[Document]) -> List[Chunk]:
        """
        Split documents into chunks.

        Args:
            documents: List of documents to split

        Returns:
            List of Chunk objects
        """
        raise NotImplementedError("Subclasses must implement split()")


class CharacterSplitter(BaseSplitter):
    """Simple character-based splitter that splits on specified separators."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        strip_separators: bool = True
    ):
        """
        Initialize the character splitter.

        Args:
            chunk_size: Maximum size of each chunk
            chunk_overlap: Overlap between chunks
            separators: List of separators to split on (in order of preference)
            strip_separators: Whether to remove separators from chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        if separators is None:
            # Default separators in order of preference
            self.separators = ["\n\n", "\n", " ", ""]
        else:
            self.separators = separators

        self.strip_separators = strip_separators

    def split(self, documents: List[Document]) -> List[Chunk]:
        """
        Split documents into chunks based on character length.

        Args:
            documents: List of documents to split

        Returns:
            List of Chunk objects
        """
        chunks = []

        for doc_idx, document in enumerate(documents):
            doc_chunks = self._split_document(document, doc_idx)
            chunks.extend(doc_chunks)

        return chunks

    def _split_document(self, document: Document, doc_idx: int) -> List[Chunk]:
        """Split a single document into chunks."""
        text = document.content
        chunks = []
        chunk_index = 0

        # Start with the entire text
        current_text = text
        start_idx = 0

        while len(current_text) > self.chunk_size:
            # Find the best separator position
            split_pos = self._find_split_position(current_text)

            # Adjust split position to stay within chunk size
            if split_pos > self.chunk_size:
                # If the best split position is too large, split at chunk_size
                split_pos = self.chunk_size

            # Create chunk
            chunk_text = current_text[:split_pos]
            chunk_id = f"{document.id}_chunk_{chunk_index}"

            # Prepare metadata for the chunk
            chunk_metadata = document.metadata.copy()
            chunk_metadata.update({
                "chunk_index": chunk_index,
                "source_document_id": document.id,
                "original_length": len(text),
                "chunk_size": len(chunk_text),
                "is_final_chunk": False
            })

            chunks.append(Chunk(
                id=chunk_id,
                content=chunk_text,
                metadata=chunk_metadata,
                source_document_id=document.id,
                chunk_index=chunk_index
            ))

            # Move to next section with overlap
            start_idx += split_pos
            overlap_start = max(0, start_idx - self.chunk_overlap)
            current_text = text[overlap_start:]

            chunk_index += 1

        # Handle the final chunk
        if current_text:
            chunk_id = f"{document.id}_chunk_{chunk_index}"
            chunk_metadata = document.metadata.copy()
            chunk_metadata.update({
                "chunk_index": chunk_index,
                "source_document_id": document.id,
                "original_length": len(text),
                "chunk_size": len(current_text),
                "is_final_chunk": True
            })

            chunks.append(Chunk(
                id=chunk_id,
                content=current_text,
                metadata=chunk_metadata,
                source_document_id=document.id,
                chunk_index=chunk_index
            ))

        return chunks

    def _find_split_position(self, text: str) -> int:
        """Find the best position to split the text."""
        for sep in self.separators:
            # Find the rightmost separator that fits within chunk size
            pos = text.rfind(sep, 0, self.chunk_size + 1)
            if pos != -1:
                # Include separator if not stripping
                if not self.strip_separators and sep:
                    pos += len(sep)
                return pos

        # If no separator found, split at chunk_size
        return self.chunk_size


class LangChainMarkdownHeaderSplitter(BaseSplitter):
    """
    Advanced splitter using LangChain's MarkdownHeaderTextSplitter.
    Splits documents based on markdown headers for better semantic coherence.
    """

    def __init__(
        self,
        headers_to_split_on=None,
        return_each_line: bool = False,
        strip_headers: bool = False
    ):
        """
        Initialize the markdown header-based splitter.

        Args:
            headers_to_split_on: Headers to split on in format [(level, name), ...]
                                e.g., [("#", "Header 1"), ("##", "Header 2")]
            return_each_line: Whether to return each line as a separate chunk
            strip_headers: Whether to strip headers from content
        """
        # Default headers to split on if not provided
        if headers_to_split_on is None:
            headers_to_split_on = [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
            ]

        self.headers_to_split_on = headers_to_split_on
        self.return_each_line = return_each_line
        self.strip_headers = strip_headers

        # Initialize LangChain splitter
        self.splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.headers_to_split_on,
            return_each_line=self.return_each_line,
            strip_headers=self.strip_headers
        )

    def split(self, documents: List[Document]) -> List[Chunk]:
        """
        Split documents into chunks based on markdown headers.

        Args:
            documents: List of documents to split

        Returns:
            List of Chunk objects
        """
        chunks = []
        total_chunks = 0

        for doc_idx, document in enumerate(documents):
            try:
                # Use LangChain's MarkdownHeaderTextSplitter
                header_chunks = self.splitter.split_text(document.content)

                # Convert LangChain documents to our Chunk format
                for i, header_chunk in enumerate(header_chunks):
                    chunk_id = f"{document.id}_chunk_{total_chunks}"

                    # Prepare metadata for the chunk
                    chunk_metadata = document.metadata.copy()
                    chunk_metadata['recipe_name'] = (
                        document.metadata.get('recipe_name')          # 优先用已有的
                        or self._extract_recipe_name(document.content) # 否则从内容提取
                    )

                    # Add header-specific metadata if available
                    header_metadata = getattr(header_chunk, 'metadata', {})
                    if header_metadata:
                        # Flatten the header metadata to avoid nested dictionaries
                        flattened_header_metadata = flatten_metadata(header_metadata)
                        chunk_metadata.update({
                            'header_info': flattened_header_metadata,
                            'has_header': True
                        })
                    else:
                        chunk_metadata['has_header'] = False

                    # Add chunk-specific metadata
                    chunk_metadata.update({
                        "chunk_index": total_chunks,
                        "source_document_id": document.id,
                        "original_length": len(document.content),
                        "chunk_size": len(header_chunk.page_content),
                        "is_final_chunk": i == len(header_chunks) - 1,
                        # "splitter_used": "LangChainMarkdownHeaderSplitter",
                        "header_level": self._detect_header_level(header_chunk.page_content)
                    })

                    chunks.append(Chunk(
                        id=chunk_id,
                        content=header_chunk.page_content,
                        metadata=chunk_metadata,
                        source_document_id=document.id,
                        chunk_index=total_chunks
                    ))

                    total_chunks += 1

            except Exception as e:
                logging.error(f"Error splitting document {document.id}: {e}")
                chunk_id = f"{document.id}_chunk_0"

                chunk_metadata = document.metadata.copy()
                chunk_metadata.update({
                    "chunk_index": 0,
                    "source_document_id": document.id,
                    "original_length": len(document.content),
                    "chunk_size": len(document.content),
                    "is_final_chunk": True,
                    # "splitter_used": "LangChainMarkdownHeaderSplitter_Fallback",
                    "header_level": 0
                })

                chunks.append(Chunk(
                    id=chunk_id,
                    content=document.content,
                    metadata=chunk_metadata,
                    source_document_id=document.id,
                    chunk_index=0
                ))

        return chunks

    def _detect_header_level(self, content: str) -> int:
        """
        Detect the highest header level in the content.

        Args:
            content: Text content to analyze

        Returns:
            Highest header level (1 for '#', 2 for '##', etc., 0 if no headers)
        """
        lines = content.split('\n')
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('#'):
                level = 0
                while level < len(stripped) and stripped[level] == '#':
                    level += 1
                if level > 0 and level < len(stripped) and stripped[level].isspace():
                    return level
        return 0
    
    def _extract_recipe_name(self, content: str) -> str:
        """从 Markdown 第一个 H1 标题提取菜谱名称。"""
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                return line.lstrip("# ").strip()
        return ""

    def _split_document(self, document: Document, doc_idx: int) -> List[Chunk]:
        """Recursively split a document using different separators."""
        text = document.content
        chunks = []
        chunk_index = 0

        # Start with largest separators and work down
        chunks = self._recursive_split(text, 0, document, chunk_index)
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.id = f"{document.id}_chunk_{i}"

        return chunks

    def _recursive_split(
        self,
        text: str,
        depth: int,
        document: Document,
        chunk_index: int
    ) -> List[Chunk]:
        """Recursively split text based on separators at different depths."""
        if len(text) <= self.chunk_size:
            # Text fits in one chunk
            chunk_id = f"{document.id}_chunk_{chunk_index}"
            chunk_metadata = document.metadata.copy()
            chunk_metadata.update({
                "chunk_index": chunk_index,
                "source_document_id": document.id,
                "original_length": len(document.content),
                "chunk_size": len(text),
                "split_depth": depth,
                "is_final_chunk": True
            })

            return [Chunk(
                id=chunk_id,
                content=text,
                metadata=chunk_metadata,
                source_document_id=document.id,
                chunk_index=chunk_index
            )]

        if depth >= len(self.separators):
            # If we've tried all separators, force split at chunk_size
            return self._force_split(text, document, chunk_index)

        # Try to split using current separator
        separator = self.separators[depth]
        if separator == "":
            # If we're at the last separator (empty string), force split
            return self._force_split(text, document, chunk_index)

        # Split by separator
        parts = text.split(separator)
        chunks = []

        current_chunk = ""
        current_idx = chunk_index

        for part in parts:
            # Test if adding this part exceeds chunk size
            test_chunk = current_chunk + separator + part if current_chunk else part

            if len(test_chunk) > self.chunk_size and current_chunk:
                # Save current chunk and start new one
                chunk_id = f"{document.id}_chunk_{current_idx}"
                chunk_metadata = document.metadata.copy()
                chunk_metadata.update({
                    "chunk_index": current_idx,
                    "source_document_id": document.id,
                    "original_length": len(document.content),
                    "chunk_size": len(current_chunk),
                    "split_depth": depth,
                    "separator_used": separator,
                    "is_final_chunk": False
                })

                chunks.append(Chunk(
                    id=chunk_id,
                    content=current_chunk,
                    metadata=chunk_metadata,
                    source_document_id=document.id,
                    chunk_index=current_idx
                ))

                # Start new chunk with overlap
                overlap_len = min(len(current_chunk), self.chunk_overlap)
                current_chunk = current_chunk[-overlap_len:] if overlap_len > 0 else ""
                current_idx += 1
                # Add the current part to the new chunk
                test_chunk = current_chunk + separator + part if current_chunk else part

            current_chunk = test_chunk

        # Handle any remaining content
        if current_chunk:
            chunk_id = f"{document.id}_chunk_{current_idx}"
            chunk_metadata = document.metadata.copy()
            chunk_metadata.update({
                "chunk_index": current_idx,
                "source_document_id": document.id,
                "original_length": len(document.content),
                "chunk_size": len(current_chunk),
                "split_depth": depth,
                "separator_used": separator,
                "is_final_chunk": True
            })

            chunks.append(Chunk(
                id=chunk_id,
                content=current_chunk,
                metadata=chunk_metadata,
                source_document_id=document.id,
                chunk_index=current_idx
            ))

        return chunks

    def _force_split(self, text: str, document: Document, chunk_index: int) -> List[Chunk]:
        """Force split text at chunk_size when no separators work."""
        chunks = []
        current_idx = chunk_index

        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk_end = min(i + self.chunk_size, len(text))
            chunk_text = text[i:chunk_end]

            chunk_id = f"{document.id}_chunk_{current_idx}"
            chunk_metadata = document.metadata.copy()
            chunk_metadata.update({
                "chunk_index": current_idx,
                "source_document_id": document.id,
                "original_length": len(document.content),
                "chunk_size": len(chunk_text),
                "split_method": "forced",
                "is_final_chunk": chunk_end == len(text)
            })

            chunks.append(Chunk(
                id=chunk_id,
                content=chunk_text,
                metadata=chunk_metadata,
                source_document_id=document.id,
                chunk_index=current_idx
            ))

            current_idx += 1

        return chunks