from dotenv import load_dotenv
import json
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

load_dotenv()

EVAL_FILE = Path("eval_records.json")
_provider = None


def get_provider():
    global _provider
    if _provider is None:
        from trulens.providers.openai import OpenAI as OpenAIProvider
        _provider = OpenAIProvider()
    return _provider


def load_records() -> list[dict]:
    if not EVAL_FILE.exists():
        return []
    return json.loads(EVAL_FILE.read_text())


def _save_record(record: dict):
    records = load_records()
    records.append(record)
    EVAL_FILE.write_text(json.dumps(records, indent=2))


def evaluate_rag(query: str, response: str, contexts: list[str], kb_id: Optional[str] = None) -> dict:
    provider = get_provider()

    # RAG Triad: Answer Relevance, Context Relevance, Groundedness
    answer_relevance = float(provider.relevance(query, response))

    ctx_scores = [float(provider.context_relevance(query, ctx)) for ctx in contexts]
    context_relevance = float(np.mean(ctx_scores)) if ctx_scores else 0.0

    groundedness_result = provider.groundedness_measure_with_cot_reasons("\n".join(contexts), response)
    groundedness = float(groundedness_result[0] if isinstance(groundedness_result, tuple) else groundedness_result)

    scores = {
        "answer_relevance": round(answer_relevance, 4),
        "context_relevance": round(context_relevance, 4),
        "groundedness": round(groundedness, 4),
        "rag_triad_avg": round((answer_relevance + context_relevance + groundedness) / 3, 4),
    }

    record = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kb_id": kb_id,
        "query": query,
        "response": response,
        "scores": scores,
    }

    _save_record(record)
    return record
