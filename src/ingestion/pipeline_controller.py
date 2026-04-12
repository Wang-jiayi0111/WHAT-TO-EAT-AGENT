"""
Module for orchestrating the ingestion pipeline.
"""
import os
from pathlib import Path
from typing import List, Optional, Union
from enum import Enum
import logging
from datetime import datetime


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


from src.ingestion.processors.loader import BaseLoader, Document
from src.ingestion.processors.splitter import BaseSplitter, Chunk
from src.ingestion.processors.transformer import BaseTransformer
from src.libs.base.vector_store import VectorStore
from src.libs.base.chroma_store import ChromaStore
from src.libs.base.file_integrity_checker import FileIntegrityChecker
from src.libs.base.bm25_indexer import BM25Indexer


class PipelineStatus(Enum):
    """Status of the ingestion pipeline."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionPipelineController:
    """Orchestrates the complete ingestion pipeline from loading to storage."""

    def __init__(
        self,
        loader: BaseLoader,
        splitter: BaseSplitter,
        transformer: BaseTransformer,
        vector_store: VectorStore,
        bm25_indexer: Optional[BM25Indexer] = None,
        integrity_checker: Optional[FileIntegrityChecker] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the ingestion pipeline controller.

        Args:
            loader: Component to load documents
            splitter: Component to split documents into chunks
            transformer: Component to transform chunks
            vector_store: Vector store for semantic search
            bm25_indexer: BM25 indexer for keyword search (optional)
            integrity_checker: File integrity checker for incremental updates (optional)
            logger: Logger instance (optional)
        """
        self.loader = loader
        self.splitter = splitter
        self.transformer = transformer
        self.vector_store = vector_store
        self.bm25_indexer = bm25_indexer
        self.integrity_checker = integrity_checker
        self.logger = logger or logging.getLogger(__name__)

        self.status = PipelineStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.documents_processed = 0
        self.chunks_created = 0
        self.errors = []

    def run(self, source: Union[str, List[str]], collection_name: str = "recipes"):
        """
        Execute the complete ingestion pipeline.

        Args:
            source: Source path(s) to process
            collection_name: Name of the collection to store vectors in

        Returns:
            Dictionary with pipeline execution results
        """
        if isinstance(source, str):
            source = [source]

        self.status = PipelineStatus.RUNNING
        self.start_time = datetime.now()
        self.documents_processed = 0
        self.chunks_created = 0
        self.errors = []

        try:
            # Initialize collections if needed
            if hasattr(self.vector_store, 'create_collection'):
                self.vector_store.create_collection(collection_name)

            if self.bm25_indexer:
                self.bm25_indexer.create_table(collection_name)

            all_chunks = []

            for src in source:
                # Step 1: Load documents
                self.logger.info(f"Loading documents from: {src}")

                # Check integrity if available
                if self.integrity_checker and os.path.isfile(src):
                    if not self.integrity_checker.should_process(src):
                        self.logger.info(f"Skipping {src} - already processed and unchanged")
                        continue

                documents = self.loader.load(src)
                self.documents_processed += len(documents)
                self.logger.info(f"Loaded {len(documents)} documents from {src}")

                # Step 2: Split documents into chunks
                self.logger.info(f"Splitting {len(documents)} documents into chunks")
                chunks = self.splitter.split(documents)
                self.chunks_created += len(chunks)
                self.logger.info(f"Created {len(chunks)} chunks from {src}")

                # Update integrity record if available
                if self.integrity_checker and os.path.isfile(src):
                    self.integrity_checker.record_processed(src)

                all_chunks.extend(chunks)

            # Step 3: Transform chunks
            self.logger.info(f"Transforming {len(all_chunks)} chunks")
            transformed_chunks = self.transformer.transform(all_chunks)
            self.logger.info("Transformation completed")

            # Step 4: Store in vector database
            self.logger.info(f"Storing {len(transformed_chunks)} chunks in vector store")

            # Prepare data for vector store
            texts = [chunk.content for chunk in transformed_chunks]
            metadatas = []
            ids = []

            for i, chunk in enumerate(transformed_chunks):
                # Combine chunk metadata with vector-specific metadata
                metadata = chunk.metadata.copy()
                metadata['chunk_id'] = chunk.id
                metadata['source_document_id'] = chunk.source_document_id
                metadata['chunk_index'] = chunk.chunk_index
                metadata['processed_at'] = datetime.now().isoformat()

                # Flatten metadata to ensure ChromaDB compatibility
                flattened_metadata = flatten_metadata(metadata)
                metadatas.append(flattened_metadata)
                ids.append(chunk.id)

            # Add to vector store
            self.vector_store.add_texts(texts, metadatas=metadatas, ids=ids)
            self.logger.info("Vector store ingestion completed")

            # Step 5: Store in BM25 index if available
            if self.bm25_indexer:
                self.logger.info(f"Storing {len(transformed_chunks)} chunks in BM25 index")

                # Prepare data for BM25 index
                bm25_documents = []
                for chunk in transformed_chunks:
                    doc_data = {
                        'id': chunk.id,
                        'content': chunk.content,
                        'collection': collection_name,
                        'metadata': {            
                            'chunk_id': chunk.id,
                            'chunk_index': chunk.chunk_index,
                            'source_document_id': chunk.source_document_id,
                            'file_path': chunk.metadata.get('file_path'),
                            'recipe_name': chunk.metadata.get('recipe_name'),
                            'source_file': chunk.metadata.get('source_file'),
                        }
                    }
                    
                    bm25_documents.append(doc_data)

                self.bm25_indexer.index_documents(bm25_documents)
                self.logger.info("BM25 index ingestion completed")

            self.status = PipelineStatus.COMPLETED
            self.end_time = datetime.now()

            duration = (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0

            result = {
                'status': self.status.value,
                'documents_processed': self.documents_processed,
                'chunks_created': self.chunks_created,
                'duration_seconds': duration,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'errors': self.errors
            }

            self.logger.info(f"Ingestion pipeline completed. Processed {self.documents_processed} documents, created {self.chunks_created} chunks in {duration:.2f}s")
            return result

        except Exception as e:
            self.status = PipelineStatus.FAILED
            self.end_time = datetime.now()
            error_msg = f"Ingestion pipeline failed: {str(e)}"
            self.errors.append(error_msg)
            self.logger.error(error_msg)

            duration = (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0

            result = {
                'status': self.status.value,
                'documents_processed': self.documents_processed,
                'chunks_created': self.chunks_created,
                'duration_seconds': duration,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'errors': self.errors
            }

            return result

    def cancel(self):
        """Cancel the running pipeline."""
        self.status = PipelineStatus.CANCELLED
        self.end_time = datetime.now()
        self.logger.info("Ingestion pipeline cancelled")

    def get_status(self):
        """Get current pipeline status."""
        return {
            'status': self.status.value,
            'documents_processed': self.documents_processed,
            'chunks_created': self.chunks_created,
            'errors': self.errors,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None
        }

    def run_incremental(self, source_dir: str, collection_name: str = "recipes"):
        """
        Run incremental ingestion, processing only changed/new files.

        Args:
            source_dir: Directory containing documents to process
            collection_name: Name of the collection to store vectors in

        Returns:
            Dictionary with pipeline execution results
        """
        if not self.integrity_checker:
            raise ValueError("Integrity checker is required for incremental ingestion")

        # Get list of files to process based on integrity check
        if not os.path.isdir(source_dir):
            raise ValueError(f"Source directory does not exist: {source_dir}")

        files_to_process = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                filepath = os.path.join(root, file)
                if self.integrity_checker.should_process(filepath):
                    files_to_process.append(filepath)

        if not files_to_process:
            self.logger.info(f"No new or changed files found in {source_dir}")
            return {
                'status': 'completed_no_changes',
                'documents_processed': 0,
                'chunks_created': 0,
                'files_checked': len(list(os.walk(source_dir))[0][2]) if os.path.exists(source_dir) else 0,
                'files_processed': 0
            }

        self.logger.info(f"Found {len(files_to_process)} files to process incrementally")
        return self.run(files_to_process, collection_name)