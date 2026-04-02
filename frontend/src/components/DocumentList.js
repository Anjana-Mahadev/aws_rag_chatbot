import React from "react";

function DocumentList({ documents, selectedDoc, onSelect, onDelete }) {
  return (
    <div className="doc-list">
      {documents.length === 0 ? (
        <p className="no-docs">No documents uploaded yet.</p>
      ) : (
        documents.map((doc) => (
          <div
            key={doc.doc_id}
            className={`doc-item${selectedDoc === doc.doc_id ? " active" : ""}`}
            onClick={() => onSelect(doc.doc_id)}
          >
            <span className="doc-icon">📄</span>
            <span className="doc-name">{doc.filename}</span>
            <span className="doc-chunks">{doc.num_chunks} chunks</span>
            <button
              className="delete-btn"
              title="Delete document"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(doc.doc_id, doc.filename);
              }}
            >
              ✕
            </button>
          </div>
        ))
      )}
    </div>
  );
}

export default DocumentList;
