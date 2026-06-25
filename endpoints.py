import shutil
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Path, Query, UploadFile, File

from kb_manager import (
    create_kb, list_kbs, update_kb, delete_kb,
    list_docs, get_doc, update_doc, delete_doc,
    safe_doc_path, require_kb,
)
from models import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBase, KnowledgeBaseListResponse,
    DocumentUpdate, DocumentInfo, DocumentListResponse, DocumentContentResponse,
    UploadResponse, MessageResponse,
    QueryRequest, QueryResponse,
    EvaluateRequest, EvalRecord, EvalRecordsResponse, LeaderboardResponse, LeaderboardAverages,
    HealthResponse,
)
from rag import get_rag_response, get_rag_context_and_response
from trulens_eval import evaluate_rag, load_records

router = APIRouter()

_404 = {404: {"description": "Resource not found"}}
_400 = {400: {"description": "Bad request / invalid input"}}
_500 = {500: {"description": "Internal server error (e.g. OpenAI call failed)"}}


# ── Health ────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Returns service status and the total number of knowledge bases on disk.",
)
async def health_check():
    return HealthResponse(status="ok", knowledge_bases=len(list_kbs()))


# ── Knowledge Bases ───────────────────────────────────────────────────────────

@router.post(
    "/knowledge-bases/",
    response_model=KnowledgeBase,
    status_code=201,
    tags=["Knowledge Bases"],
    summary="Create a knowledge base",
    description="Create a named knowledge base. Choose `faiss` (fast, in-memory) or `chroma` (persistent on disk) as the vector store.",
    responses={**_400},
)
async def create_knowledge_base(payload: KnowledgeBaseCreate):
    return create_kb(payload)


@router.get(
    "/knowledge-bases/",
    response_model=KnowledgeBaseListResponse,
    tags=["Knowledge Bases"],
    summary="List all knowledge bases",
    description="Returns every knowledge base with its metadata and current document count.",
)
async def list_knowledge_bases():
    kbs = list_kbs()
    return KnowledgeBaseListResponse(knowledge_bases=kbs, count=len(kbs))


@router.get(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBase,
    tags=["Knowledge Bases"],
    summary="Get a knowledge base",
    description="Retrieve metadata for a single knowledge base by its ID.",
    responses={**_404},
)
async def get_knowledge_base(
    kb_id: str = Path(..., description="Knowledge base ID, e.g. `kb_a1b2c3d4`"),
):
    return require_kb(kb_id)


@router.put(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBase,
    tags=["Knowledge Bases"],
    summary="Update a knowledge base",
    description="Update the `name` and/or `description` of an existing knowledge base. The vector store type cannot be changed after creation.",
    responses={**_404, **_400},
)
async def update_knowledge_base(
    kb_id: str,
    payload: KnowledgeBaseUpdate,
):
    return update_kb(kb_id, payload)


@router.delete(
    "/knowledge-bases/{kb_id}",
    status_code=204,
    tags=["Knowledge Bases"],
    summary="Delete a knowledge base",
    description="Permanently delete a knowledge base along with all its documents and vector store data. This action is irreversible.",
    responses={**_404},
)
async def delete_knowledge_base(kb_id: str):
    delete_kb(kb_id)


# ── Documents ─────────────────────────────────────────────────────────────────

@router.get(
    "/knowledge-bases/{kb_id}/documents/",
    response_model=DocumentListResponse,
    tags=["Documents"],
    summary="List documents",
    description="List all `.txt` documents stored in a knowledge base, with file metadata.",
    responses={**_404},
)
async def list_documents(kb_id: str):
    docs = [DocumentInfo(**d) for d in list_docs(kb_id)]
    return DocumentListResponse(documents=docs, count=len(docs))


@router.post(
    "/knowledge-bases/{kb_id}/documents/upload",
    response_model=UploadResponse,
    tags=["Documents"],
    summary="Upload a document",
    description="Upload a `.txt` file into the knowledge base. The file will be indexed the next time a query is made.",
    responses={**_404, **_400},
)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(..., description="A plain-text `.txt` file to add to the knowledge base"),
):
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")
    path = safe_doc_path(kb_id, file.filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return UploadResponse(message=f"'{file.filename}' uploaded to '{kb_id}'", name=file.filename)


@router.get(
    "/knowledge-bases/{kb_id}/documents/{name}",
    response_model=DocumentContentResponse,
    tags=["Documents"],
    summary="Get a document",
    description="Read the full text content and metadata of a single document.",
    responses={**_404},
)
async def get_document(
    kb_id: str,
    name: str = Path(..., description="Document filename, e.g. `my_document.txt`"),
):
    return DocumentContentResponse(**get_doc(kb_id, name))


@router.put(
    "/knowledge-bases/{kb_id}/documents/{name}",
    response_model=MessageResponse,
    tags=["Documents"],
    summary="Update a document",
    description="Replace the full text content of an existing document. The document will be re-indexed on the next query.",
    responses={**_404, **_400},
)
async def update_document(
    kb_id: str,
    name: str,
    payload: DocumentUpdate,
):
    update_doc(kb_id, name, payload.content)
    return MessageResponse(message=f"'{name}' updated in '{kb_id}'")


@router.delete(
    "/knowledge-bases/{kb_id}/documents/{name}",
    status_code=204,
    tags=["Documents"],
    summary="Delete a document",
    description="Remove a single document from the knowledge base. The vector index will no longer include it on the next query.",
    responses={**_404},
)
async def delete_document(kb_id: str, name: str):
    delete_doc(kb_id, name)


# ── Query ─────────────────────────────────────────────────────────────────────

@router.post(
    "/knowledge-bases/{kb_id}/query/",
    response_model=QueryResponse,
    tags=["Query"],
    summary="Query a knowledge base",
    description=(
        "Retrieve relevant document chunks from the knowledge base and generate an answer using the RAG pipeline. "
        "Requires at least one document to be uploaded and a valid OpenAI API key."
    ),
    responses={**_404, **_500},
)
async def query_knowledge_base(
    kb_id: str,
    request: QueryRequest,
):
    require_kb(kb_id)
    try:
        response = await get_rag_response(request.query, kb_id)
        return QueryResponse(kb_id=kb_id, query=request.query, response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Evaluation (TruLens RAG Triad) ────────────────────────────────────────────

@router.post(
    "/knowledge-bases/{kb_id}/evaluate/",
    response_model=EvalRecord,
    tags=["Evaluation"],
    summary="Evaluate a query (RAG Triad)",
    description=(
        "Run a query through the RAG pipeline and score the result using the **TruLens RAG Triad**:\n\n"
        "- **Answer Relevance** (0–1): Is the response relevant to the query?\n"
        "- **Context Relevance** (0–1): Is the retrieved context relevant to the query?\n"
        "- **Groundedness** (0–1): Is the response supported by the retrieved context?\n\n"
        "All three scores are averaged into `rag_triad_avg`. "
        "Each evaluation call uses additional OpenAI tokens for LLM-based scoring."
    ),
    responses={**_404, **_500},
)
async def evaluate_knowledge_base(
    kb_id: str,
    request: EvaluateRequest,
):
    require_kb(kb_id)
    try:
        response, contexts = await get_rag_context_and_response(request.query, kb_id)
        record = evaluate_rag(request.query, response, contexts, kb_id=kb_id)
        return EvalRecord(**record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/evaluate/records",
    response_model=EvalRecordsResponse,
    tags=["Evaluation"],
    summary="List evaluation records",
    description="Retrieve past TruLens evaluation records. Optionally filter by knowledge base and paginate with `limit` and `offset`.",
)
async def get_evaluation_records(
    kb_id: Optional[str] = Query(None, description="Filter records to a specific knowledge base ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip (for pagination)"),
):
    records = load_records()
    if kb_id:
        records = [r for r in records if r.get("kb_id") == kb_id]
    total = len(records)
    page = records[offset: offset + limit]
    return EvalRecordsResponse(records=[EvalRecord(**r) for r in page], total=total)


@router.get(
    "/evaluate/leaderboard",
    response_model=LeaderboardResponse,
    tags=["Evaluation"],
    summary="Evaluation leaderboard",
    description=(
        "Aggregate RAG Triad scores across all evaluation records. "
        "Filter by `kb_id` to see stats for a single knowledge base. "
        "Returns `null` averages if no records exist yet."
    ),
)
async def get_leaderboard(
    kb_id: Optional[str] = Query(None, description="Filter to a specific knowledge base ID"),
):
    records = load_records()
    if kb_id:
        records = [r for r in records if r.get("kb_id") == kb_id]
    if not records:
        return LeaderboardResponse(
            total_evaluations=0,
            kb_id=kb_id,
            averages=None,
            message="No evaluation records yet — run POST /knowledge-bases/{kb_id}/evaluate/ first",
        )
    scores = [r["scores"] for r in records]
    return LeaderboardResponse(
        total_evaluations=len(records),
        kb_id=kb_id,
        averages=LeaderboardAverages(
            answer_relevance=round(float(np.mean([s["answer_relevance"] for s in scores])), 4),
            context_relevance=round(float(np.mean([s["context_relevance"] for s in scores])), 4),
            groundedness=round(float(np.mean([s["groundedness"] for s in scores])), 4),
            rag_triad_avg=round(float(np.mean([s["rag_triad_avg"] for s in scores])), 4),
        ),
    )
