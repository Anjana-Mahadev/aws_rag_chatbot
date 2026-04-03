import React, { useState, useRef } from "react";
import { uploadPDF } from "../api";

function FileUpload({ onUploadComplete }) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState(null); // { type, message }
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef();

  const handleFile = async (file) => {
    if (!file) return;
    if (file.type !== "application/pdf") {
      setStatus({ type: "error", message: "Please select a PDF file." });
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setStatus({ type: "error", message: "File too large (max 50 MB)." });
      return;
    }

    setUploading(true);
    setStatus({ type: "loading", message: `Uploading ${file.name}...` });

    try {
      const result = await uploadPDF(file);
      setStatus({ type: "success", message: `"${result.filename}" indexed (${result.num_chunks} chunks)` });
      onUploadComplete(result);
      // Clear success message after 3 seconds
      setTimeout(() => setStatus(null), 3000);
    } catch (err) {
      const msg = err.response?.data?.detail || "Upload failed. Is the backend running?";
      setStatus({ type: "error", message: msg });
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  return (
    <div className="upload-section">
      <div
        className={`drop-zone${dragging ? " dragging" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <span className="upload-icon">☁️</span>
        <p><strong>Drop your PDF here</strong><br/>or click to browse files</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          hidden
          onChange={(e) => handleFile(e.target.files[0])}
        />
      </div>
      <div className="upload-limits">Max 50 MB · 500 pages · 5 documents</div>
      <div className="upload-warning">⚠️ Documents are auto-deleted when you close this tab.</div>
      {status && (
        <div className={`upload-status ${status.type}`}>{status.message}</div>
      )}
    </div>
  );
}

export default FileUpload;
