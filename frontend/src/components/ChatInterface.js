import React, { useState, useRef, useEffect } from "react";
import { queryDocument } from "../api";

function ChatInterface({ docId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const messagesEndRef = useRef(null);

  // Reset chat when document changes
  useEffect(() => {
    setMessages([]);
    setInput("");
    setChatHistory([]);
  }, [docId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendQuestion = async (question, skipAutocorrect = false) => {
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      const result = await queryDocument(docId, question, chatHistory, skipAutocorrect);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer,
          citations: result.citations,
          followups: result.followups,
          retrievalMethod: result.retrieval_method,
          suggestedCorrection: result.suggested_correction,
        },
      ]);
      // Update conversation memory
      setChatHistory((prev) => [
        ...prev,
        { question, answer: result.answer },
      ]);
    } catch (err) {
      const msg = err.response?.data?.detail || "Something went wrong.";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${msg}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question) return;
    sendQuestion(question);
  };

  const handleFollowup = (question) => {
    sendQuestion(question, true); // skip autocorrect for suggested questions
  };

  const handleUseCorrected = (corrected) => {
    sendQuestion(corrected, true); // skip autocorrect since it's already corrected
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      <div className="chat-header">
        <span className="status-dot"></span>
        <span className="chat-title">Chat with your document</span>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="placeholder">
            <span className="placeholder-icon">🔍</span>
            <p>Ask a question about this document</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`msg-row ${msg.role}`}>
            <div className="msg-avatar">
              {msg.role === "user" ? "You" : "AI"}
            </div>
            <div className="msg-bubble">
              {msg.suggestedCorrection && (
                <div className="correction-suggestion">
                  ✨ Did you mean:{" "}
                  <button
                    className="correction-btn"
                    onClick={() => handleUseCorrected(msg.suggestedCorrection)}
                    disabled={loading}
                  >
                    "{msg.suggestedCorrection}"
                  </button>
                </div>
              )}
              {msg.content}
              {msg.retrievalMethod && (
                <div className="retrieval-badge">
                  <span className="retrieval-icon">⚡</span> {msg.retrievalMethod}
                </div>
              )}
              {msg.citations && msg.citations.length > 0 && (
                <div className="citations">
                  <strong>📌 Citations:</strong>
                  {msg.citations.map((c, j) => (
                    <div key={j} className="citation-item">
                      <span className="citation-page">{c.pages}</span>
                      <span className="citation-snippet">{c.snippet}</span>
                    </div>
                  ))}
                </div>
              )}
              {msg.followups && msg.followups.length > 0 && (
                <div className="followups">
                  <strong>💡 Follow-up questions:</strong>
                  <div className="followup-chips">
                    {msg.followups.map((q, j) => (
                      <button
                        key={j}
                        className="followup-chip"
                        onClick={() => handleFollowup(q)}
                        disabled={loading}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="typing-indicator">
            <div className="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about this document..."
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>
          <span>Send →</span>
        </button>
      </div>
    </>
  );
}

export default ChatInterface;
