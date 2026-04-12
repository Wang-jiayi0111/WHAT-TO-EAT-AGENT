"""
Main entrypoint for the ingestion pipeline of the WHAT-TO-EAT-AGENT.
"""
import argparse
import sys
import os
from pathlib import Path

# Add src to path so we can import modules
current_file_path = Path(__file__).resolve()
src_dir = current_file_path.parent.parent  # Go up twice from src/ingestion/ to get src/
project_root = current_file_path.parent.parent.parent  # Go up thrice to get project root

# Add both to path to handle different execution contexts
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ingestion.processors.loader import DirectoryLoader, MarkdownLoader
from src.ingestion.processors.splitter import LangChainMarkdownHeaderSplitter
from src.ingestion.processors.transformer import (
    TextCleaner,
    MetadataEnricher,
    RecipeSpecificTransformer,
    CompositeTransformer
)
from src.ingestion.pipeline_controller import IngestionPipelineController
from src.ingestion.document_manager import DocumentManager
from src.libs.base.chroma_store import ChromaStore
from src.libs.base.bm25_indexer import BM25Indexer
from src.libs.base.file_integrity_checker import FileIntegrityChecker
from src.libs.adapters.embed.embed_factory import EmbedFactory
from src.libs.base.settings import Settings


def create_default_pipeline(data_dir: str = "data/recipes", collection_name: str = "recipes"):
    """
    Create a default ingestion pipeline with standard configuration.

    Args:
        data_dir: Directory containing recipe files to ingest
        collection_name: Name of the collection to store vectors in

    Returns:
        IngestionPipelineController configured with default components
    """
    # Create loader - loads markdown files from a directory
    loader = DirectoryLoader(loader_map={".md": MarkdownLoader()})

    # Create splitter - splits documents into chunks based on markdown headers
    splitter = LangChainMarkdownHeaderSplitter(
        headers_to_split_on=[
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ],
        strip_headers=False  # Keep headers as they provide important context
    )

    # Create transformer - cleans and enriches chunks
    text_cleaner = TextCleaner(
        remove_extra_whitespace=True,
        remove_extra_newlines=False,
        remove_special_chars=False
    )
    metadata_enricher = MetadataEnricher()
    recipe_transformer = RecipeSpecificTransformer()

    transformer = CompositeTransformer([
        text_cleaner,
        metadata_enricher,
        recipe_transformer
    ])

    # Create vector store
    settings = Settings()
    embedding_fn = EmbedFactory.get_embed(settings)
    persist_path = "./data/db"
    vector_store = ChromaStore(
        db_path=persist_path, 
        embedding_function=embedding_fn,
        collection_name="recipes"
    )
    # Create BM25 indexer
    bm25_indexer = BM25Indexer(db_path="data/db/bm25_index.db")

    # Create integrity checker for incremental updates
    integrity_checker = FileIntegrityChecker(db_path="data/db/integrity.db")

    # Create document manager
    document_manager = DocumentManager(
        vector_store=vector_store,
        bm25_indexer=bm25_indexer,
        collection_name=collection_name
    )

    # Create pipeline controller
    controller = IngestionPipelineController(
        loader=loader,
        splitter=splitter,
        transformer=transformer,
        vector_store=vector_store,  # Using vector store directly for pipeline
        bm25_indexer=bm25_indexer,
        integrity_checker=integrity_checker
    )

    return controller


def main():
    """Main entrypoint for the ingestion pipeline."""
    parser = argparse.ArgumentParser(description="WHAT-TO-EAT-AGENT Ingestion Pipeline")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="data/recipes",
        help="Directory containing recipe files to ingest (default: data/recipes)"
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default="recipes",
        help="Name of the collection to store vectors in (default: recipes)"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Perform incremental ingestion (only process changed files)"
    )

    args = parser.parse_args()

    print(f"Starting ingestion pipeline for directory: {args.input_dir}")
    print(f"Collection name: {args.collection_name}")
    print(f"Incremental mode: {args.incremental}")

    # Create the default pipeline
    controller = create_default_pipeline(args.input_dir, args.collection_name)

    # Check if input directory exists
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    try:
        if args.incremental:
            # Run incremental ingestion
            result = controller.run_incremental(args.input_dir, args.collection_name)
            print(f"Incremental ingestion completed: {result}")
        else:
            # Run full ingestion
            result = controller.run(args.input_dir, args.collection_name)
            print(f"Ingestion completed: {result}")

        if result.get('status') in ['completed', 'completed_no_changes']:
            print("Pipeline completed successfully!")
            print(f"Documents processed: {result.get('documents_processed', 0)}")
            print(f"Chunks created: {result.get('chunks_created', 0)}")
            print(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")
        else:
            print(f"Pipeline failed with errors: {result.get('errors', [])}")
            sys.exit(1)

    except Exception as e:
        print(f"Pipeline failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()