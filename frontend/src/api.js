import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000/api";

let _sessionId = sessionStorage.getItem("session_id") || "";

const api = axios.create({ baseURL: API_BASE });

// Attach session ID to every request
api.interceptors.request.use((config) => {
  if (_sessionId) {
    config.headers["X-Session-Id"] = _sessionId;
  }
  return config;
});

export async function initSession() {
  if (_sessionId) {
    // Session exists (e.g. page reload) — ping to re-register with server
    await api.post("/session/ping").catch(() => {});
    return _sessionId;
  }
  const res = await api.post("/session");
  _sessionId = res.data.session_id;
  sessionStorage.setItem("session_id", _sessionId);
  return _sessionId;
}

export function getSessionId() {
  return _sessionId;
}

export async function uploadPDF(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function queryDocument(docId, question, chatHistory = [], skipAutocorrect = false) {
  const res = await api.post("/query", {
    doc_id: docId,
    question,
    chat_history: chatHistory,
    skip_autocorrect: skipAutocorrect,
  });
  return res.data;
}

export async function getDocuments() {
  const res = await api.get("/documents");
  return res.data.documents;
}

export async function deleteDocument(docId) {
  const res = await api.delete(`/documents/${docId}`);
  return res.data;
}

export function pingSession() {
  // Lightweight heartbeat — keeps the session alive on the server
  return api.post("/session/ping").catch(() => {});
}

export function cleanupSession() {
  // Fire-and-forget cleanup on tab close — sendBeacon guarantees delivery
  if (_sessionId) {
    const url = `${API_BASE}/session/cleanup`;
    const blob = new Blob([JSON.stringify({})], { type: "application/json" });
    // sendBeacon doesn't support custom headers, so pass session ID as query param
    navigator.sendBeacon(`${url}?session_id=${_sessionId}`, blob);
  }
}
