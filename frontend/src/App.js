import React, { useState, useEffect } from "react";
import FileUpload from "./components/FileUpload";
import ChatInterface from "./components/ChatInterface";
import DocumentList from "./components/DocumentList";
import { getDocuments, deleteDocument, initSession, pingSession } from "./api";
import "./App.css";

function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);

  const refreshDocs = async () => {
    try {
      const docs = await getDocuments();
      setDocuments(docs);
      // Auto-select first document if none selected
      if (docs.length > 0) {
        setSelectedDoc((prev) => prev || docs[0].doc_id);
      }
    } catch {
      // backend may not be ready yet
    }
  };

  // Initialize session, then load documents
  useEffect(() => {
    initSession().then(() => refreshDocs());
  }, []);

  // Heartbeat: ping server every 30s to keep session alive
  useEffect(() => {
    const interval = setInterval(() => {
      pingSession();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  // Warn user when closing tab (documents will be cleaned up by server)
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (documents.length > 0) {
        e.preventDefault();
        e.returnValue = "Your uploaded documents will be deleted after you leave. Continue?";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [documents]);

  const handleUploadComplete = (newDoc) => {
    setDocuments((prev) => [
      ...prev,
      { doc_id: newDoc.doc_id, filename: newDoc.filename, num_chunks: newDoc.num_chunks },
    ]);
    setSelectedDoc(newDoc.doc_id);
  };

  const handleDelete = async (docId, filename) => {
    if (!window.confirm(`Delete "${filename}"? This removes the PDF and its index.`)) return;
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      if (selectedDoc === docId) {
        setSelectedDoc(null);
      }
    } catch {
      alert("Failed to delete document.");
    }
  };

  return (
    <div className="app">
      <div className="app-bg">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
      </div>

      <header className="app-header">
        <div className="header-brand">
          <div className="brand-logo-wrap">
            <svg className="brand-logo" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="docGrad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#818cf8" />
                  <stop offset="100%" stopColor="#6366f1" />
                </linearGradient>
                <linearGradient id="sparkGrad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#c4b5fd" />
                  <stop offset="100%" stopColor="#f0abfc" />
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="2" result="blur" />
                  <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
              </defs>
              {/* Background hexagon */}
              <path d="M26 4 L44 15 L44 37 L26 48 L8 37 L8 15 Z" fill="url(#docGrad)" opacity="0.15" />
              <path d="M26 4 L44 15 L44 37 L26 48 L8 37 L8 15 Z" stroke="url(#docGrad)" strokeWidth="1.2" fill="none" opacity="0.5" />
              {/* Document page */}
              <rect x="16" y="12" width="18" height="24" rx="2.5" fill="rgba(255,255,255,0.08)" stroke="#a5b4fc" strokeWidth="1.5" />
              <path d="M28 12 L34 18" stroke="#a5b4fc" strokeWidth="1.2" />
              <path d="M28 12 L28 18 L34 18" stroke="#a5b4fc" strokeWidth="1.2" fill="rgba(99,102,241,0.2)" />
              {/* Text lines */}
              <path d="M20 22h10M20 25.5h8M20 29h6" stroke="#c4b5fd" strokeWidth="1.3" strokeLinecap="round" opacity="0.8" />
              {/* AI sparkle */}
              <g filter="url(#glow)">
                <path d="M40 8 L41.5 12 L40 16 L38.5 12 Z" fill="url(#sparkGrad)" />
                <path d="M36 12 L40 10.5 L44 12 L40 13.5 Z" fill="url(#sparkGrad)" />
              </g>
              {/* Small sparkle */}
              <g filter="url(#glow)" opacity="0.7">
                <path d="M12 38 L13 40.5 L12 43 L11 40.5 Z" fill="#c4b5fd" />
                <path d="M10 40.5 L12 39.5 L14 40.5 L12 41.5 Z" fill="#c4b5fd" />
              </g>
              {/* Question mark bubble */}
              <circle cx="40" cy="36" r="7" fill="url(#docGrad)" stroke="#818cf8" strokeWidth="1" />
              <text x="40" y="39.5" textAnchor="middle" fill="white" fontSize="10" fontWeight="700" fontFamily="sans-serif">?</text>
            </svg>
          </div>
          <h1>PDF Q&A Assistant</h1>
        </div>
        <p>Upload documents and get AI-powered answers instantly</p>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <h3 className="sidebar-title">Documents</h3>
          <FileUpload onUploadComplete={handleUploadComplete} />
          <DocumentList
            documents={documents}
            selectedDoc={selectedDoc}
            onSelect={setSelectedDoc}
            onDelete={handleDelete}
          />
        </aside>

        <main className="chat-area">
          {selectedDoc ? (
            <ChatInterface docId={selectedDoc} />
          ) : (
            <div className="placeholder">
              <span className="placeholder-icon">💬</span>
              <p>Select a document to start chatting</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
