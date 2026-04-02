import os
import uuid

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from config import UPLOAD_DIR
from services.pdf_service import chunk_pages, extract_pages_from_pdf
from services.s3_service import delete_file_from_s3, list_documents, upload_file_to_s3
from services.vector_store import build_vector_store, delete_vector_store, get_indexed_documents

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
MAX_DOCUMENTS = 5               # max documents stored at once
MAX_PAGES = 500                  # max pages per PDF


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...), x_session_id: str = Header(default="")):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    session_id = x_session_id

    # Check document count limit (per session)
    existing_docs = [d for d in get_indexed_documents() if d.get("session_id") == session_id]
    if len(existing_docs) >= MAX_DOCUMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_DOCUMENTS} documents allowed. Delete one first."
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50 MB)")

    doc_id = str(uuid.uuid4())
    safe_filename = os.path.basename(file.filename or "document.pdf")
    local_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{safe_filename}")

    with open(local_path, "wb") as f:
        f.write(content)

    try:
        # Upload to S3
        s3_key = f"documents/{doc_id}_{safe_filename}"
        s3_uri = upload_file_to_s3(local_path, s3_key)

        # Extract text per page and build vector store
        pages = extract_pages_from_pdf(local_path)
        full_text = "\n".join(pages)
        if not full_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")

        # Check page count
        from pypdf import PdfReader
        page_count = len(PdfReader(local_path).pages)
        if page_count > MAX_PAGES:
            raise HTTPException(status_code=400, detail=f"PDF too long ({page_count} pages). Max {MAX_PAGES} pages.")

        chunks = chunk_pages(pages)
        build_vector_store(doc_id, chunks, safe_filename, session_id=session_id)

        return {
            "doc_id": doc_id,
            "filename": safe_filename,
            "s3_uri": s3_uri,
            "num_chunks": len(chunks),
            "message": "Document uploaded and indexed successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)


@router.get("/documents")
def get_documents(x_session_id: str = Header(default="")):
    docs = get_indexed_documents()
    # Only return documents belonging to this session
    filtered = [d for d in docs if d.get("session_id") == x_session_id]
    return {"documents": filtered}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, x_session_id: str = Header(default="")):
    # Get metadata to find S3 key
    docs = get_indexed_documents()
    doc_meta = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not doc_meta:
        raise HTTPException(status_code=404, detail="Document not found")

    # Only allow deleting own session's documents
    if doc_meta.get("session_id") != x_session_id:
        raise HTTPException(status_code=403, detail="You can only delete your own documents")

    # Delete from S3
    s3_key = f"documents/{doc_id}_{doc_meta['filename']}"
    delete_file_from_s3(s3_key)

    # Delete vector store
    delete_vector_store(doc_id)

    return {"message": "Document deleted successfully"}


@router.delete("/documents")
def delete_all_documents(x_session_id: str = Header(default="")):
    """Delete all documents belonging to this session — used for tab-close cleanup."""
    docs = get_indexed_documents()
    session_docs = [d for d in docs if d.get("session_id") == x_session_id]
    for doc in session_docs:
        s3_key = f"documents/{doc['doc_id']}_{doc['filename']}"
        try:
            delete_file_from_s3(s3_key)
        except Exception:
            pass
        try:
            delete_vector_store(doc["doc_id"])
        except Exception:
            pass
    return {"message": f"Deleted {len(session_docs)} document(s)"}
