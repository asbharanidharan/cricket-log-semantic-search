# Cricket Log Semantic Search & RAG System

An AI-powered cricket log analysis platform that combines semantic search, metadata filtering, Retrieval-Augmented Generation (RAG), data-quality validation and Model Context Protocol (MCP) integration.

The system allows users to search structured cricket records, ask natural-language questions, retrieve relevant records and identify potential inconsistencies in stored data.

## Project Overview

This project demonstrates an end-to-end AI-powered search and question-answering system built around cricket match logs.

It processes cricket records, stores structured data in MongoDB, generates vector embeddings and indexes them in Qdrant. A Django REST API provides search and RAG capabilities, while a Dash frontend provides an interactive interface.

An MCP server exposes the system's capabilities as tools that can be accessed by compatible MCP clients.

**Dataset:** 500 synthetic cricket records.

> The dataset is synthetic and intended for demonstrating search, retrieval and validation functionality. It does not represent verified real-world cricket match data.

## Key Features

### 1. Semantic Search
- Converts natural-language queries into vector embeddings.
- Uses Sentence Transformers (`all-MiniLM-L6-v2`).
- Retrieves semantically relevant cricket records through Qdrant.
- Returns similarity scores with search results.

### 2. Exact Metadata Filtering
Supports filtering using:
- Player
- Team
- Event
- Exact runs
- Minimum runs
- Maximum runs

Multiple metadata filters can be combined.

### 3. Retrieval-Augmented Generation (RAG)
- Accepts natural-language questions.
- Retrieves relevant cricket records.
- Uses an Ollama-hosted LLM to generate answers.
- Provides supporting source records.
- Distinguishes stored information from verified real-world facts.

### 4. Data Quality Validation
Implements rule-based validation to identify potential inconsistencies.

Examples include:
- Six-hit and runs mismatches.
- Suspicious boundary-run values.
- Empty commentary placeholders.
- Missing player or location context.
- Records requiring manual review.

Each record can include:
- Validation warning codes.
- Warning severity.
- Review status.
- Data-quality classification.
- Review requirement indicators.

Validation warnings are indicators for further investigation, not proof that a record is factually incorrect.

### 5. MCP Integration

The MCP server exposes three tools:

| Tool | Function |
|---|---|
| `search_cricket_logs` | Semantic search and exact metadata filtering |
| `ask_cricket_question` | Natural-language RAG question answering |
| `get_cricket_statistics` | Qdrant collection statistics and health information |

### 6. Interactive Dashboard
Built using Dash.

Provides:
- Cricket record search.
- AI-powered question answering.
- Search result tables.
- Validation warning visibility.
- Compact source-record presentation.

## Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python |
| Backend | Django, Django REST Framework |
| Database | MongoDB |
| Vector Database | Qdrant |
| Embeddings | Sentence Transformers |
| LLM | Ollama, Llama 3.2 (3B) |
| Frontend | Plotly Dash |
| AI Architecture | RAG, Semantic Search |
| Integration | Model Context Protocol (MCP) |
| Containerization | Podman |
| Development | VS Code, Git |

## System Architecture

```text
             Cricket Log Dataset
                     |
                     v
               Data Ingestion
                     |
             +-------+-------+
             |               |
             v               v
          MongoDB        Text Processing
                             |
                             v
                       Embeddings
                             |
                             v
                          Qdrant
                             |
                             v
                    Django REST API
                             |
                  +----------+----------+
                  |                     |
                  v                     v
             Dash Frontend          MCP Server
                  |                     |
                  v                     v
             User Queries          MCP Clients
                  |
                  v
             RAG Pipeline
                  |
                  v
              Ollama LLM
                  |
                  v
          Answer + Source Records
```

## API Endpoints

The Django backend exposes the following endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/search/` | GET | Search cricket records |
| `/api/chat/` | POST | Ask natural-language questions |

### Search API Example

```http
GET /api/search/?player=Player%202&limit=5
```

### Chat API Example

```json
{
  "question": "Show all records for Player 2."
}
```

The chat response includes the generated answer, retrieval method, matching records and validation information.

## Project Testing

The following functionality was tested during development:

- Player-based filtering.
- Combined player and event filtering.
- Exact numeric filtering.
- Inclusive numeric range filtering.
- Exact event retrieval.
- Semantic search fallback.
- Validation warning generation.
- Source-record retrieval.
- Django API integration.
- Dash frontend functionality.
- MCP tool execution.

### Observed Dataset Statistics

| Metric | Value |
|---|---:|
| Stored Qdrant records | 500 |
| Player 2 records | 33 |
| Player 2 records with validation warnings | 14 |
| Player 2 high-severity warning records | 2 |

These are observed results from the synthetic dataset and should not be interpreted as actual cricket statistics.

## Data Quality and Limitations

- The dataset contains synthetic records.
- Rule-based validation identifies potential inconsistencies but cannot independently establish factual accuracy.
- Semantic retrieval returns a limited number of relevant records based on similarity.
- LLM-generated explanations may contain unsupported interpretations despite prompt constraints.
- External authoritative cricket data is not currently used to verify individual records.
- Qdrant vector indexing statistics must be interpreted alongside actual search behaviour.

## Future Improvements

- Improve LLM evidence grounding and source attribution.
- Introduce authoritative cricket data verification.
- Expand validation rules and record-level confidence reporting.
- Improve retrieval evaluation using precision and recall metrics.
- Add automated testing and monitoring.
- Improve pagination and search performance.

## Project Objective

The primary objective is to demonstrate how vector databases, semantic retrieval, LLMs, data validation and MCP can be integrated into a practical AI-powered information retrieval application.

The project explores the complete workflow from structured data ingestion to intelligent search, contextual question answering and tool-based integration.
