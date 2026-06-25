from dotenv import load_dotenv
import json
import os
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAI

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")


def _vector_store_type(kb_id: str) -> str:
    meta_path = Path("data") / kb_id / "metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text()).get("vector_store", "faiss")
    return "faiss"


def setup_rag_system(kb_id: str):
    docs_dir = Path("data") / kb_id / "documents"
    vs_type = _vector_store_type(kb_id)

    documents = []
    for txt_file in sorted(docs_dir.glob("*.txt")):
        loader = TextLoader(str(txt_file), encoding="utf-8")
        documents.extend(loader.load())

    if not documents:
        raise ValueError(f"No documents in knowledge base '{kb_id}' — upload at least one .txt file first")

    chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(documents)
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

    if vs_type == "chroma":
        from langchain_chroma import Chroma
        persist_dir = str(Path("data") / kb_id / "vector_store")
        vector_store = Chroma.from_documents(chunks, embeddings, persist_directory=persist_dir)
    else:
        vector_store = FAISS.from_documents(chunks, embeddings)

    return vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 5})


async def get_rag_context_and_response(query: str, kb_id: str) -> tuple[str, list[str]]:
    llm = OpenAI(openai_api_key=openai_api_key)
    retriever = setup_rag_system(kb_id)

    retrieved_docs = retriever.invoke(query)
    contexts = [doc.page_content for doc in retrieved_docs]
    context = "\n".join(contexts)

    prompt = [f"Use the following information to answer the question:\n\n{context}\n\nQuestion: {query}"]
    result = llm.generate(prompt)
    response_text = result.generations[0][0].text.strip()

    return response_text, contexts


async def get_rag_response(query: str, kb_id: str) -> str:
    response_text, _ = await get_rag_context_and_response(query, kb_id)
    return response_text
