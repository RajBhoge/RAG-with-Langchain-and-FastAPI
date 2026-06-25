from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


# ── Enums ─────────────────────────────────────────────────────────────────────

class VectorStoreType(str, Enum):
    faiss = "faiss"
    chroma = "chroma"


# ── Knowledge Base schemas ─────────────────────────────────────────────────────

class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the knowledge base", examples=["Product Docs"])
    description: str = Field("", max_length=500, description="What this knowledge base is about", examples=["Customer-facing product documentation"])
    vector_store: VectorStoreType = Field(VectorStoreType.faiss, description="Vector store backend — faiss (in-memory, fast) or chroma (disk-persistent)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Product Docs",
                "description": "Customer-facing product documentation",
                "vector_store": "faiss",
            }
        }
    }


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New name for the knowledge base")
    description: Optional[str] = Field(None, max_length=500, description="New description")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Updated Product Docs",
                "description": "Revised customer documentation",
            }
        }
    }


class KnowledgeBase(BaseModel):
    id: str = Field(..., description="Auto-generated knowledge base ID", examples=["kb_a1b2c3d4"])
    name: str = Field(..., description="Knowledge base name")
    description: str = Field(..., description="Description")
    vector_store: VectorStoreType = Field(..., description="Vector store backend in use")
    created_at: str = Field(..., description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 last-updated timestamp")
    document_count: int = Field(..., ge=0, description="Number of .txt documents currently in this KB")


class KnowledgeBaseListResponse(BaseModel):
    knowledge_bases: list[KnowledgeBase]
    count: int = Field(..., ge=0, description="Total number of knowledge bases")


# ── Document schemas ───────────────────────────────────────────────────────────

class DocumentInfo(BaseModel):
    name: str = Field(..., description="Filename of the document")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    last_modified: str = Field(..., description="ISO 8601 last-modified timestamp")


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    count: int = Field(..., ge=0, description="Number of documents in this knowledge base")


class DocumentContentResponse(BaseModel):
    name: str = Field(..., description="Filename")
    content: str = Field(..., description="Full text content of the document")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    last_modified: str = Field(..., description="ISO 8601 last-modified timestamp")
    word_count: int = Field(..., ge=0, description="Number of words in the document")


class DocumentUpdate(BaseModel):
    content: str = Field(..., min_length=1, description="Replacement text content for the document")

    model_config = {
        "json_schema_extra": {
            "example": {"content": "This is the updated content of the document."}
        }
    }


class UploadResponse(BaseModel):
    message: str = Field(..., description="Human-readable result message")
    name: str = Field(..., description="Filename that was uploaded")


class MessageResponse(BaseModel):
    message: str = Field(..., description="Human-readable result message")


# ── Query schemas ──────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="The question to ask the knowledge base")

    model_config = {
        "json_schema_extra": {
            "example": {"query": "What do polar bears eat?"}
        }
    }


class QueryResponse(BaseModel):
    kb_id: str = Field(..., description="Knowledge base that was queried")
    query: str = Field(..., description="The original question")
    response: str = Field(..., description="Generated answer from the RAG pipeline")


# ── Evaluation schemas ─────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="The question to run and evaluate")

    model_config = {
        "json_schema_extra": {
            "example": {"query": "How do polar bears survive in the cold?"}
        }
    }


class EvalScores(BaseModel):
    answer_relevance: float = Field(..., ge=0.0, le=1.0, description="How relevant the answer is to the query (0–1)")
    context_relevance: float = Field(..., ge=0.0, le=1.0, description="How relevant retrieved chunks are to the query (0–1)")
    groundedness: float = Field(..., ge=0.0, le=1.0, description="How well the answer is supported by retrieved context (0–1)")
    rag_triad_avg: float = Field(..., ge=0.0, le=1.0, description="Average of the three RAG Triad scores")


class EvalRecord(BaseModel):
    id: str = Field(..., description="Unique record ID (timestamp-based)")
    timestamp: str = Field(..., description="ISO 8601 evaluation timestamp")
    kb_id: Optional[str] = Field(None, description="Knowledge base that was evaluated")
    query: str = Field(..., description="The query that was evaluated")
    response: str = Field(..., description="The generated response that was evaluated")
    scores: EvalScores


class EvalRecordsResponse(BaseModel):
    records: list[EvalRecord]
    total: int = Field(..., ge=0, description="Total records matching the filter (before limit/offset)")


class LeaderboardAverages(BaseModel):
    answer_relevance: float = Field(..., description="Mean answer relevance across all evaluations")
    context_relevance: float = Field(..., description="Mean context relevance across all evaluations")
    groundedness: float = Field(..., description="Mean groundedness across all evaluations")
    rag_triad_avg: float = Field(..., description="Mean RAG Triad average across all evaluations")


class LeaderboardResponse(BaseModel):
    total_evaluations: int = Field(..., ge=0, description="Number of evaluation records included")
    kb_id: Optional[str] = Field(None, description="Knowledge base filter applied, if any")
    averages: Optional[LeaderboardAverages] = Field(None, description="Aggregate scores — null if no records exist")
    message: Optional[str] = Field(None, description="Informational message when no records are available")


# ── System schemas ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status", examples=["ok"])
    knowledge_bases: int = Field(..., ge=0, description="Total number of knowledge bases on disk")
