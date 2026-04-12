"""
Module for loading documents in various formats.
"""
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Document:
    """Represents a loaded document."""
    id: str
    content: str
    metadata: Dict[str, any]
    source: str
    format: str

class BaseLoader:
    """Abstract base class for all loaders."""

    def load(self, source: str) -> List[Document]:
        """
        Load documents from the given source.

        Args:
            source: Path or identifier for the data source

        Returns:
            List of Document objects
        """
        raise NotImplementedError("Subclasses must implement load()")

class MarkdownLoader(BaseLoader):
    """Loader for Markdown files."""

    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding

    def load(self, source: str) -> List[Document]:
        """
        Load a markdown file and return a list of documents.

        Args:
            source: Path to the markdown file

        Returns:
            List of Document objects
        """
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {source}")

        if source_path.suffix.lower() != ".md":
            raise ValueError(f"Expected markdown file, got: {source_path.suffix}")

        with open(source_path, 'r', encoding=self.encoding) as f:
            content = f.read()

        doc_id = str(source_path.absolute())

        document = Document(
            id=doc_id,
            content=content,
            metadata={
                "source_file": str(source_path.name),
                "file_path": str(source_path.absolute()),
                "file_size": source_path.stat().st_size,
                # "encoding": self.encoding,
                "recipe_name": str(source_path.stem)
            },
            source=str(source_path),
            format="markdown"
        )

        logger.info(f"Loaded markdown document from {source}")
        return [document]

class DirectoryLoader(BaseLoader):
    """Loader that recursively loads documents from a directory."""

    def __init__(self, loader_map: Optional[Dict[str, BaseLoader]] = None):
        """
        Initialize the directory loader.

        Args:
            loader_map: Mapping of file extensions to loaders (default supports .md)
        """
        if loader_map is None:
            self.loader_map = {".md": MarkdownLoader()}
        else:
            self.loader_map = loader_map

    def load(self, source: str) -> List[Document]:
        """
        Load all supported documents from a directory.

        Args:
            source: Path to the directory

        Returns:
            List of Document objects
        """
        source_path = Path(source)
        if not source_path.is_dir():
            raise ValueError(f"Source is not a directory: {source}")

        documents = []

        for file_path in source_path.rglob("*"):
            if file_path.is_file():
                loader = self.loader_map.get(file_path.suffix.lower())
                if loader:
                    try:
                        loaded_docs = loader.load(str(file_path))
                        documents.extend(loaded_docs)
                        logger.info(f"Loaded {len(loaded_docs)} documents from {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to load {file_path}: {e}")

        logger.info(f"Total documents loaded from directory {source}: {len(documents)}")
        return documents