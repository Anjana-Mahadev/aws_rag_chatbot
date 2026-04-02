import asyncio
import time
import uuid

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from routes.upload import router as upload_router
from routes.query import router as query_router
from services.vector_store import get_indexed_documents, delete_vector_store
from services.s3_service import delete_file_from_s3

# Heartbeat tracking: sessions that haven't pinged in this many seconds are cleaned up
HEARTBEAT_TTL_SECONDS = 1800  # 30 minutes without a ping → session expired
CLEANUP_INTERVAL = 300        # check every 5 minutes

# In-memory session heartbeat tracker: {session_id: last_ping_timestamp}
_session_heartbeats: dict[str, float] = {}

app = FastAPI(title="PDF Q&A with AWS Bedrock", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api", tags=["Upload"])
app.include_router(query_router, prefix="/api", tags=["Query"])


@app.post("/api/session")
def create_session():
    """Create a new anonymous session for user isolation."""
    sid = str(uuid.uuid4())
    _session_heartbeats[sid] = time.time()
    return {"session_id": sid}


@app.post("/api/session/ping")
def ping_session(x_session_id: str = Header(default="")):
    """Heartbeat ping — keeps the session alive. Also re-registers sessions after server restart."""
    if x_session_id:
        _session_heartbeats[x_session_id] = time.time()
    return {"status": "ok"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


async def _cleanup_expired_sessions():
    """Background task: delete documents from sessions that stopped sending heartbeats."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        try:
            now = time.time()
            cutoff = now - HEARTBEAT_TTL_SECONDS
            orphan_cutoff = now - HEARTBEAT_TTL_SECONDS  # 30 min for orphans too

            # Find expired sessions (ones we're tracking that stopped pinging)
            expired_sessions = {
                sid for sid, last_ping in _session_heartbeats.items()
                if last_ping < cutoff
            }

            docs = get_indexed_documents()
            count = 0
            for doc in docs:
                session_id = doc.get("session_id", "")
                should_delete = False

                if session_id in expired_sessions:
                    # Tracked session that expired
                    should_delete = True
                elif session_id and session_id not in _session_heartbeats:
                    # Orphaned doc — session never registered (server restarted, old data)
                    # Delete if created_at is old enough
                    created = doc.get("created_at", 0)
                    if created and created < orphan_cutoff:
                        should_delete = True
                elif not session_id:
                    # Legacy doc with no session — always clean up
                    should_delete = True

                if should_delete:
                    s3_key = f"documents/{doc['doc_id']}_{doc['filename']}"
                    try:
                        delete_file_from_s3(s3_key)
                    except Exception:
                        pass
                    try:
                        delete_vector_store(doc["doc_id"])
                    except Exception:
                        pass
                    count += 1

            # Remove expired sessions from tracker
            for sid in expired_sessions:
                _session_heartbeats.pop(sid, None)

            if count:
                print(f"[Cleanup] Removed {count} document(s)")
        except Exception as e:
            print(f"[Cleanup] Error: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_cleanup_expired_sessions())
