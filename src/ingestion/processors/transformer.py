"""
Module for transforming document chunks (cleaning, normalization, enrichment).
"""
from typing import List
from abc import ABC, abstractmethod
import re
import unicodedata
from src.ingestion.processors.splitter import Chunk


class BaseTransformer(ABC):
    """Abstract base class for all transformers."""

    @abstractmethod
    def transform(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Transform a list of chunks.

        Args:
            chunks: List of chunks to transform

        Returns:
            Transformed list of chunks
        """
        pass


class TextCleaner(BaseTransformer):
    """Cleans and normalizes text in chunks."""

    def __init__(
        self,
        remove_extra_whitespace: bool = True,
        remove_accents: bool = False,
        lowercase: bool = False,
        remove_special_chars: bool = False,
        remove_extra_newlines: bool = True
    ):
        """
        Initialize the text cleaner.

        Args:
            remove_extra_whitespace: Remove extra whitespace characters
            remove_accents: Remove accents from characters
            lowercase: Convert text to lowercase
            remove_special_chars: Remove special characters (keeps alphanumerics and basic punctuation)
            remove_extra_newlines: Remove extra newlines
        """
        self.remove_extra_whitespace = remove_extra_whitespace
        self.remove_accents = remove_accents
        self.lowercase = lowercase
        self.remove_special_chars = remove_special_chars
        self.remove_extra_newlines = remove_extra_newlines

    def transform(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Apply cleaning transformations to chunks.

        Args:
            chunks: List of chunks to transform

        Returns:
            Cleaned list of chunks
        """
        transformed_chunks = []

        for chunk in chunks:
            # Apply transformations to content
            cleaned_content = chunk.content

            if self.remove_extra_newlines:
                # Replace multiple newlines with single newlines
                cleaned_content = re.sub(r'\n\s*\n', '\n\n', cleaned_content)
                # Remove leading/trailing newlines
                cleaned_content = cleaned_content.strip('\n')

            if self.remove_accents:
                # Normalize and remove accents
                cleaned_content = unicodedata.normalize('NFD', cleaned_content)
                cleaned_content = ''.join(
                    char for char in cleaned_content
                    if unicodedata.category(char) != 'Mn'  # Mn = Nonspacing_Mark (accents)
                )

            if self.remove_extra_whitespace:
                # Replace multiple whitespaces with single space
                cleaned_content = re.sub(r'\s+', ' ', cleaned_content)

            if self.remove_special_chars:
                # Keep only alphanumeric, basic punctuation, and whitespace
                cleaned_content = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', cleaned_content)
                # Clean up any extra spaces created
                if self.remove_extra_whitespace:
                    cleaned_content = re.sub(r'\s+', ' ', cleaned_content)

            if self.lowercase:
                cleaned_content = cleaned_content.lower()

            # Create a new chunk with the cleaned content
            cleaned_chunk = Chunk(
                id=chunk.id,
                content=cleaned_content,
                metadata=chunk.metadata.copy(),
                source_document_id=chunk.source_document_id,
                chunk_index=chunk.chunk_index
            )

            # Update metadata to indicate transformation applied
            cleaned_chunk.metadata['transformer'] = 'TextCleaner'
            cleaned_chunk.metadata['text_cleaned'] = True

            transformed_chunks.append(cleaned_chunk)

        return transformed_chunks


class MetadataEnricher(BaseTransformer):
    """Enriches chunk metadata with additional information."""

    def __init__(self, include_word_count: bool = True, include_char_count: bool = True):
        """
        Initialize the metadata enricher.

        Args:
            include_word_count: Include word count in metadata
            include_char_count: Include character count in metadata
        """
        self.include_word_count = include_word_count
        self.include_char_count = include_char_count

    def transform(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Enrich chunk metadata with additional information.

        Args:
            chunks: List of chunks to transform

        Returns:
            Chunks with enriched metadata
        """
        enriched_chunks = []

        for chunk in chunks:
            # Calculate statistics
            content = chunk.content
            char_count = len(content)
            word_count = len(content.split())

            # Create a new chunk with enriched metadata
            enriched_chunk = Chunk(
                id=chunk.id,
                content=chunk.content,
                metadata=chunk.metadata.copy(),
                source_document_id=chunk.source_document_id,
                chunk_index=chunk.chunk_index
            )

            # Add enriched metadata
            if self.include_char_count:
                enriched_chunk.metadata['char_count'] = char_count
            if self.include_word_count:
                enriched_chunk.metadata['word_count'] = word_count

            # Add transformer info
            enriched_chunk.metadata['transformer'] = 'MetadataEnricher'
            enriched_chunk.metadata['metadata_enriched'] = True

            enriched_chunks.append(enriched_chunk)

        return enriched_chunks


class CompositeTransformer(BaseTransformer):
    """Applies a sequence of transformers to chunks."""

    def __init__(self, transformers: List[BaseTransformer]):
        """
        Initialize the composite transformer.

        Args:
            transformers: List of transformers to apply in sequence
        """
        self.transformers = transformers

    def transform(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Apply all transformers in sequence to the chunks.

        Args:
            chunks: List of chunks to transform

        Returns:
            Transformed list of chunks
        """
        transformed_chunks = chunks

        for transformer in self.transformers:
            transformed_chunks = transformer.transform(transformed_chunks)

        return transformed_chunks


class RecipeSpecificTransformer(BaseTransformer):
    """Transformer tailored for recipe content."""

    def transform(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Apply recipe-specific transformations to chunks.

        Args:
            chunks: List of chunks to transform

        Returns:
            Transformed list of chunks
        """
        transformed_chunks = []

        for chunk in chunks:
            # Apply recipe-specific transformations
            transformed_content = chunk.content

            # Normalize ingredient lists (convert different bullet points to consistent format)
            transformed_content = re.sub(r'^\s*[\*\-\•]\s*', '- ', transformed_content, flags=re.MULTILINE)
            transformed_content = re.sub(r'^\s*\d+[\.:\)]\s*', '', transformed_content, flags=re.MULTILINE)

            # Standardize heading formats
            # Convert ATX-style headers (# Header) to consistent format
            transformed_content = re.sub(r'^\s*(#{1,6})\s+(.+)$', r'\1 \2', transformed_content, flags=re.MULTILINE)

            # Identify and tag recipe sections if recognized
            if any(keyword in transformed_content.lower() for keyword in ['ingredients', 'directions', 'instructions']):
                # Add section type to metadata
                if 'ingredients' in transformed_content.lower():
                    chunk.metadata['section_type'] = 'ingredients'
                elif any(kw in transformed_content.lower() for kw in ['directions', 'instructions', 'steps']):
                    chunk.metadata['section_type'] = 'instructions'

            # Create a new chunk with transformed content
            transformed_chunk = Chunk(
                id=chunk.id,
                content=transformed_content,
                metadata=chunk.metadata.copy(),
                source_document_id=chunk.source_document_id,
                chunk_index=chunk.chunk_index
            )

            # Update metadata to indicate transformation applied
            transformed_chunk.metadata['transformer'] = 'RecipeSpecificTransformer'
            transformed_chunk.metadata['recipe_transformed'] = True

            transformed_chunks.append(transformed_chunk)

        return transformed_chunks