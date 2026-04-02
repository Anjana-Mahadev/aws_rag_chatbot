# PDF Q&A — Ask your Documents (AWS Bedrock + FAISS)

A full-stack web app where users upload PDFs and ask questions answered by AI using retrieval-augmented generation (RAG).

## Architecture

```
React Frontend (port 3000)
        ↓
FastAPI Backend (port 8000)
        ↓
AWS S3 (document storage) — ap-south-1
        ↓
FAISS (local vector search)
        ↓
Local Embeddings (sentence-transformers, FREE)
        ↓
AWS Bedrock (Claude 3 Haiku) — us-east-1
```

## Cost

| Component | Cost |
|---|---|
| Embeddings | **FREE** — local sentence-transformers |
| S3 | **FREE tier** — 5 GB, 20K GET, 2K PUT/month |
| Bedrock (Claude 3 Haiku) | ~$0.001 per query |
| EC2 (t2.micro) | **FREE tier** — 750 hrs/month for 12 months |

## Prerequisites

- Python 3.10+
- Node.js 18+
- `tesseract-ocr` and `poppler-utils` (for scanned PDF support)
- AWS account with:
  - S3 access
  - Bedrock access (Claude 3 Haiku enabled in us-east-1)

## Setup

### 1. Configure AWS Credentials

Copy the env file and fill in your credentials:

```bash
cp .env.example backend/.env
```

Edit `backend/.env`:
```
AWS_ACCESS_KEY_ID=YOUR_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET
AWS_REGION=ap-south-1
S3_BUCKET_NAME=my-pdf-qa-bucket
BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```

### 2. Install System Dependencies

```bash
sudo apt install tesseract-ocr poppler-utils
```

### 3. Start the Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm start
```

The app opens at **http://localhost:3000**.

## API Endpoints

| Method | Endpoint               | Description                  |
|--------|------------------------|------------------------------|
| POST   | `/api/upload`          | Upload a PDF file            |
| GET    | `/api/documents`       | List all indexed documents   |
| DELETE | `/api/documents/{id}`  | Delete a document + index    |
| POST   | `/api/query`           | Ask a question about a doc   |
| GET    | `/api/health`          | Health check                 |

### Upload Example

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@document.pdf"
```

### Query Example

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "uuid-from-upload", "question": "What is this document about?"}'
```

## How It Works

1. **Upload**: PDF is stored in S3, text is extracted per page (with OCR fallback for scanned PDFs), chunked into ~1000-char segments with page tracking
2. **Index**: Each chunk is embedded using a free local model (sentence-transformers) and stored in a local FAISS index + BM25 sparse index
3. **Query**: User's question is auto-corrected for spelling, then searched via hybrid retrieval (FAISS dense + BM25 sparse, fused with Reciprocal Rank Fusion). Conversation history from the session is included for context-aware follow-ups
4. **Answer**: Retrieved chunks + question + chat history are sent to Claude 3 Haiku via Bedrock for the final answer, with page-level citations
5. **Follow-ups**: A second LLM call generates 3 suggested follow-up questions displayed as clickable chips

## Upload Limits

| Limit | Value |
|---|---|
| File size | 50 MB per PDF |
| Page count | 500 pages max |
| Total documents | 5 max (delete old to add new) |
| File type | PDF only |

## 🔒 User Isolation

Each browser tab gets a unique anonymous session. Users can only see, query, and delete their own documents. When a user closes the tab, their documents are automatically cleaned up from S3 and the vector store.

## Features

- Drag & drop PDF upload
- Chat-style Q&A interface
- **Conversation Memory**: Maintains context across follow-up questions within a session — ask "what about chapter 3?" after a previous answer and it understands
- **Follow-up Suggestions**: After each answer, 3 AI-generated follow-up questions appear as clickable chips to keep exploration flowing
- **Hybrid search**: FAISS dense + BM25 sparse retrieval with RRF fusion
- **Citations**: Answers include page numbers and text snippets from the source PDF
- **Auto-correct**: Spelling mistakes in questions are corrected before retrieval
- **User Isolation**: Each browser tab gets a unique session — users only see their own documents
- **Auto-cleanup**: Documents are automatically deleted 30 minutes after the user closes the tab
- Greetings and general questions handled
- OCR support for scanned/image PDFs
- Delete documents (removes S3 file + vector index)
- Auto-selects document on upload/page load

## Deploying to EC2

1. Launch an EC2 instance (Ubuntu, t2.micro free tier, **30 GB EBS**)
2. Install Python 3.10+, Node.js 18+, tesseract-ocr, poppler-utils
3. Clone the repo, set up `backend/.env`
4. Run backend with: `uvicorn main:app --host 0.0.0.0 --port 8000`
5. Build frontend: `npm run build`, serve with nginx or similar
6. Open port 8000 (API) and 80/443 (frontend) in security groups

> **Note:** t2.micro has 1 GB RAM. PyTorch + sentence-transformers is tight. Consider t3.small if you hit memory issues.
