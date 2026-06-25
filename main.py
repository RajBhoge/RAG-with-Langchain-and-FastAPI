from fastapi import FastAPI
from endpoints import router

tags_metadata = [
    {
        "name": "System",
        "description": "Health check and service status.",
    },
    {
        "name": "Knowledge Bases",
        "description": "Create, list, update, and delete knowledge bases. Each KB has its own documents and vector store.",
    },
    {
        "name": "Documents",
        "description": "Upload, read, update, and delete `.txt` documents within a knowledge base.",
    },
    {
        "name": "Query",
        "description": "Ask questions against a knowledge base using the RAG pipeline.",
    },
    {
        "name": "Evaluation",
        "description": "Evaluate RAG quality using the **TruLens RAG Triad** (Answer Relevance, Context Relevance, Groundedness).",
    },
]

app = FastAPI(
    title="Knowledge Assistant API",
    description=(
        "A RAG-powered knowledge assistant built with **LangChain** and **FastAPI**.\n\n"
        "Upload documents into named knowledge bases, query them with natural language, "
        "and evaluate response quality using the **TruLens RAG Triad**."
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
)

app.include_router(router)
