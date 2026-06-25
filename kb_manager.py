import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from models import KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate

DATA_ROOT = Path("data")
DATA_ROOT.mkdir(exist_ok=True)


def _kb_path(kb_id: str) -> Path:
    return DATA_ROOT / kb_id


def _docs_path(kb_id: str) -> Path:
    return _kb_path(kb_id) / "documents"


def _meta_path(kb_id: str) -> Path:
    return _kb_path(kb_id) / "metadata.json"


def _load_meta(kb_id: str) -> dict | None:
    p = _meta_path(kb_id)
    return json.loads(p.read_text()) if p.exists() else None


def _save_meta(data: dict):
    _meta_path(data["id"]).write_text(json.dumps(data, indent=2))


def _doc_count(kb_id: str) -> int:
    d = _docs_path(kb_id)
    return len(list(d.glob("*.txt"))) if d.exists() else 0


def _to_kb(meta: dict) -> KnowledgeBase:
    return KnowledgeBase(**{**meta, "document_count": _doc_count(meta["id"])})


def require_kb(kb_id: str) -> KnowledgeBase:
    meta = _load_meta(kb_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
    return _to_kb(meta)


# ── KB CRUD ───────────────────────────────────────────────────────────────────

def create_kb(payload: KnowledgeBaseCreate) -> KnowledgeBase:
    kb_id = f"kb_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    _docs_path(kb_id).mkdir(parents=True)
    (_kb_path(kb_id) / "vector_store").mkdir()
    meta = {
        "id": kb_id,
        "name": payload.name,
        "description": payload.description,
        "vector_store": payload.vector_store.value,
        "created_at": now,
        "updated_at": now,
    }
    _save_meta(meta)
    return _to_kb(meta)


def list_kbs() -> list[KnowledgeBase]:
    result = []
    for p in DATA_ROOT.iterdir():
        if p.is_dir() and (p / "metadata.json").exists():
            meta = _load_meta(p.name)
            if meta:
                result.append(_to_kb(meta))
    return sorted(result, key=lambda kb: kb.created_at)


def update_kb(kb_id: str, payload: KnowledgeBaseUpdate) -> KnowledgeBase:
    meta = _load_meta(kb_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
    if payload.name is not None:
        meta["name"] = payload.name
    if payload.description is not None:
        meta["description"] = payload.description
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_meta(meta)
    return _to_kb(meta)


def delete_kb(kb_id: str):
    p = _kb_path(kb_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
    shutil.rmtree(p)


# ── Document management ───────────────────────────────────────────────────────

def safe_doc_path(kb_id: str, name: str) -> Path:
    filename = os.path.basename(name)
    if not filename or filename != name or not filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Document name must be a plain .txt filename with no path separators")
    return _docs_path(kb_id) / filename


def list_docs(kb_id: str) -> list[dict]:
    require_kb(kb_id)
    return [
        {
            "name": f.name,
            "size_bytes": f.stat().st_size,
            "last_modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        }
        for f in sorted(_docs_path(kb_id).glob("*.txt"))
    ]


def get_doc(kb_id: str, name: str) -> dict:
    require_kb(kb_id)
    path = safe_doc_path(kb_id, name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{name}' not found in '{kb_id}'")
    content = path.read_text(encoding="utf-8")
    stat = path.stat()
    return {
        "name": name,
        "content": content,
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "word_count": len(content.split()),
    }


def update_doc(kb_id: str, name: str, content: str):
    require_kb(kb_id)
    path = safe_doc_path(kb_id, name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{name}' not found in '{kb_id}'")
    path.write_text(content, encoding="utf-8")
    meta = _load_meta(kb_id)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_meta(meta)


def delete_doc(kb_id: str, name: str):
    require_kb(kb_id)
    path = safe_doc_path(kb_id, name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{name}' not found in '{kb_id}'")
    path.unlink()
    meta = _load_meta(kb_id)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_meta(meta)
