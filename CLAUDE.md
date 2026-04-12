# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

The WHAT-TO-EAT-AGENT is an intelligent meal planning assistant that combines RAG (Retrieval-Augmented Generation) technology with MCP (Model Context Protocol) to provide personalized recipe recommendations. The system features multi-user support with individual dietary profiles, inventory tracking, and contextual meal planning capabilities.

## Architecture

The system consists of several interconnected components:

1. **Agent Logic Layer** (`src/agent/`): LangGraph-based workflow orchestrator with intent routing
2. **MCP Server Layer** (`src/mcp/`): Standardized protocol interface for recipe tools
3. **RAG Engine** (`src/rag/`): Retrieval pipeline with hybrid search (dense + sparse)
4. **Ingestion Pipeline** (`src/ingestion/`): Data processing from Markdown recipes to vector storage
5. **Persistence Layer** (`src/libs/base/`): SQLite databases for user profiles, inventory, and history
6. **Adapters** (`src/libs/adapters/`): Pluggable interfaces for LLMs, embeddings, and vector stores

## Key Features

- **Multi-user Support**: Individual dietary restrictions, preferences, and cooking habits
- **Inventory Tracking**: Real-time tracking of available ingredients
- **Personalized Recommendations**: Recipe suggestions based on user profiles and available ingredients
- **MCP Integration**: Standardized protocol for consumption by AI assistants
- **Modular Architecture**: Pluggable components for LLMs, embeddings, and storage backends

## Directory Structure

```
WHAT-TO-EAT-AGENT/
├── config/                 # Configuration files
├── data/                   # Persistent data (databases, recipes)
│   ├── db/                 # SQLite databases
│   └── recipes/            # Markdown recipe files
├── logs/                   # Application logs
├── src/                    # Source code
│   ├── agent/              # LangGraph agent logic
│   ├── mcp/                # MCP server implementation
│   ├── ingestion/          # Data ingestion pipeline
│   ├── observability/      # Monitoring and dashboard
│   ├── rag/                # RAG core components
│   └── libs/               # Shared libraries and adapters
├── tests/                  # Unit, integration, and end-to-end tests
├── pyproject.toml          # Dependencies and configuration
└── config/setting.yaml     # Runtime configuration
```

## Common Commands

### Running the Application

```bash
# Run with default behavior (ingest and interactive mode)
python src/main.py

# Run only the ingestion pipeline
python src/main.py --ingest

# Run in interactive mode only
python src/main.py --interactive

# Run the MCP server
python src/main.py --mcp-server

# Run with custom data directory
python src/main.py --data-dir path/to/recipes

# Run incremental ingestion (only process changed files)
python src/main.py --ingest --incremental
```

### Testing

```bash
# Run all tests
pytest

# Run specific test directory
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_main_app.py

# Run with coverage
pytest --cov=src
```

### Configuration

- Main configuration is in `config/setting.yaml`
- Database paths and settings can be adjusted in the `databases` section
- LLM provider settings (currently configured for DashScope/Qwen) are in the `llm` section
- Embedding and retrieval parameters can be tuned in respective sections

## Development Guidelines

### Adding New Recipe Formats

1. Create a new loader in `src/ingestion/processors/`
2. Register it in the ingestion pipeline in `src/main.py`
3. Update the `LangChainMarkdownHeaderSplitter` if needed for new structural patterns

### Extending MCP Tools

1. Create a new tool class inheriting from `RecipeRetrievalTool` in `src/mcp/server.py`
2. Register the tool in the `MCPRecipeServer` initialization
3. Implement the execute method with proper error handling

### Modifying the Agent Workflow

1. The main state machine is defined in `src/agent/state.py`
2. Intent routing logic is in `src/agent/nodes/router.py`
3. Each node implementation is in `src/agent/nodes/`
4. The workflow orchestration is in `src/agent/workflow.py`

### Database Schema Changes

- User profiles are stored in `data/db/user_profiles.db`
- Inventory is managed in `data/db/inventory.db`
- Ingestion history is tracked in `data/db/integrity.db`
- Vector data uses Chroma at `data/db/chroma/`

## Key Classes and Modules

- `WhatToEatAgent` (main.py): Main application class
- `MCPRecipeServer` (mcp/server.py): MCP protocol implementation
- `RAGEngine` (rag/core.py): Core retrieval logic
- `AgentState` (agent/state.py): State management for the workflow
- `IngestionPipelineController` (ingestion/pipeline_controller.py): Data ingestion orchestration
- Various adapter classes in `src/libs/adapters/`: Pluggable LLM/embedding/vector store implementations

## Testing Approach

The project follows a test-driven development approach with three layers:

1. **Unit Tests** (`tests/unit/`): Individual component testing
2. **Integration Tests** (`tests/integration/`): Multi-component workflow testing
3. **End-to-End Tests** (`tests/e2e/`): Complete scenario testing

## Troubleshooting

- If recipes aren't being found, check if the ingestion pipeline ran successfully
- If dietary restrictions aren't being applied, verify the user profile is correctly configured
- If the MCP server isn't responding, ensure the configuration in `config/setting.yaml` is correct
- Check logs in `logs/` directory for detailed error information