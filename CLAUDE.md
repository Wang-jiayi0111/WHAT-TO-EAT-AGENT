# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The WHAT-TO-EAT-AGENT is an intelligent meal planning assistant that implements a sophisticated RAG (Retrieval Augmented Generation) system for personalized recipe recommendations. The system features multi-user support, inventory tracking, dietary constraint handling, and integrates with the Model Context Protocol (MCP) for seamless interaction with AI assistants like GitHub Copilot.

## Architecture

The system follows a layered architecture:

- **Agent Layer** (`src/agent/`): Orchestrates the main application logic using LangGraph, including intent routing, memory management, and logistics coordination
- **MCP Server Layer** (`src/mcp/`): Provides standardized tools for recipe retrieval using the Model Context Protocol
- **Ingestion Pipeline** (`src/ingestion/`): Handles document processing, chunking, and indexing of recipe knowledge base
- **Libraries** (`src/libs/`): Core abstractions and utilities for LLM providers, embeddings, and data handling
- **Observability** (`src/observability/`): Tracking and visualization tools for monitoring the RAG pipeline

## Key Components

- **Recipe Researcher**: Performs RAG retrieval using hybrid search (dense + sparse) with reranking
- **Memory Keeper**: Maintains user profiles, dietary restrictions, and preferences in `data/db/user_profiles.db`
- **Logistics Manager**: Tracks household inventory and generates shopping lists in `data/db/inventory.db`
- **MCP Integration**: Allows the system to work seamlessly with AI coding assistants via standardized protocols

## Common Development Commands

### Testing
- Run all tests: `pytest`
- Run specific test file: `pytest tests/test_filename.py`
- Run with coverage: `pytest --cov=src tests/`

### Running the Application
- Start the MCP server: `python src/mcp/server.py`
- Start the observability dashboard: `streamlit run src/observability/dashboard/app.py`
- Process new recipes: `python -m src.ingestion.pipeline`

### Configuration
The system is configured via `config/settings.yaml` which manages LLM providers, embedding models, vector stores, and other settings.

## Data Storage

- User profiles: `data/db/user_profiles.db`
- Inventory tracking: `data/db/inventory.db`
- Ingestion history: `data/db/ingestion_history.db`
- BM25 index: `data/db/bm25_index.db`
- Vector storage: `data/vector/chroma/`
- System logs: `logs/traces.jsonl`

## Specialized Tools & Libraries

- LangGraph for agent orchestration
- ChromaDB for vector storage
- SQLite for structured data persistence
- MCP (Model Context Protocol) for integration with coding assistants
- Streamlit for observability dashboard
- Various LLM providers supported via abstract interfaces (OpenAI, Azure OpenAI, Ollama, DashScope)

## Development Guidelines

- Use the factory pattern for LLM and embedding provider abstraction
- Maintain traceability through the observability system
- Follow the RAG pipeline patterns for document ingestion and retrieval
- Respect the multi-user architecture when implementing features
- Leverage the MCP protocol for integration with AI assistants