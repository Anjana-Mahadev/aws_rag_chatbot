import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from spellchecker import SpellChecker

from services.llm_service import ask_llm, chat_general, generate_followups
from services.vector_store import search_vector_store

router = APIRouter()

_spell = SpellChecker()

_GREETING_WORDS = {"hi", "hello", "hey", "hola", "greetings", "good morning",
                   "good afternoon", "good evening", "good night", "sup", "yo",
                   "howdy", "namaste", "thanks", "thank you", "bye", "goodbye"}


def _autocorrect(text: str) -> str:
    """Correct misspelled words in the query."""
    words = text.split()
    corrected = []
    for word in words:
        # Preserve punctuation attached to word
        stripped = word.strip("?!.,;:")
        if not stripped:
            corrected.append(word)
            continue
        # Skip technical terms: mixed case (ByteNet), contains digits (S2S),
        # all-caps (FAISS), or capitalized words (proper nouns)
        if (any(c.isupper() for c in stripped[1:])   # mixed case like ByteNet, ConvS2S
            or any(c.isdigit() for c in stripped)      # contains numbers like S2S, GPT4
            or stripped[0].isupper()                    # capitalized like Transformer
            or stripped.isupper()):                     # all-caps like FAISS, RRF
            corrected.append(word)
            continue
        correction = _spell.correction(stripped.lower())
        if correction and correction != stripped.lower():
            # Preserve original casing style and surrounding punctuation
            prefix = word[:len(word) - len(word.lstrip("?!.,;:"))]
            suffix = word[len(word.rstrip("?!.,;:")):]  if word != word.rstrip("?!.,;:") else ""
            corrected.append(prefix + correction + suffix)
        else:
            corrected.append(word)
    return " ".join(corrected)


def _is_general_question(text: str) -> bool:
    """Detect greetings and non-document questions."""
    stripped = text.strip().lower().rstrip("!?.")
    if stripped in _GREETING_WORDS:
        return True
    if any(stripped.startswith(w) for w in ("who are you", "what can you do",
           "how are you", "what are you", "help")):
        return True
    return False


class ChatHistoryItem(BaseModel):
    question: str
    answer: str


class QueryRequest(BaseModel):
    doc_id: str
    question: str
    chat_history: list[ChatHistoryItem] = []
    skip_autocorrect: bool = False


@router.post("/query")
def query_document(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Handle greetings and general questions without hitting the vector store
    if _is_general_question(req.question):
        answer = chat_general(req.question)
        return {"answer": answer, "citations": []}

    # Autocorrect: suggest but don't force
    original_question = req.question.strip()
    suggested_correction = None
    if not req.skip_autocorrect:
        corrected = _autocorrect(original_question)
        if corrected.lower() != original_question.lower():
            suggested_correction = corrected

    # Always search and answer with the original question
    query_text = original_question

    try:
        relevant_chunks = search_vector_store(req.doc_id, query_text)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail="Document not found. Please upload it first."
        )

    if not relevant_chunks:
        return {
            "answer": "No relevant content found in the document.",
            "citations": [],
        }

    # Extract text for LLM context
    chunk_texts = [c["text"] for c in relevant_chunks]
    history_dicts = [h.model_dump() for h in req.chat_history]

    start_time = time.time()
    llm_result = ask_llm(query_text, chunk_texts, chat_history=history_dicts)
    latency = round(time.time() - start_time, 2)

    answer = llm_result["answer"]
    input_tokens = llm_result["input_tokens"]
    output_tokens = llm_result["output_tokens"]

    # Generate follow-up suggestions
    followups = generate_followups(query_text, answer, chunk_texts)

    # Build citations with page numbers
    citations = []
    for c in relevant_chunks:
        pages = c.get("pages", [])
        if pages:
            page_str = ", ".join(str(p) for p in pages)
            label = f"Page {page_str}" if len(pages) == 1 else f"Pages {page_str}"
        else:
            label = "Page unknown"
        snippet = c["text"][:150].replace("\n", " ").strip() + "..."
        citations.append({"pages": label, "snippet": snippet})

    response = {
        "answer": answer,
        "citations": citations,
        "followups": followups,
        "retrieval_method": "Hybrid Search (FAISS Dense + BM25 Sparse · RRF Fusion)",
        "metrics": {
            "latency_seconds": latency,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "chunks_used": len(relevant_chunks),
        },
    }
    if suggested_correction:
        response["suggested_correction"] = suggested_correction
    return response
