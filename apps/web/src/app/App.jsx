import { useEffect, useRef, useState } from "react";
import Sidebar from "../features/documents/Sidebar.jsx";
import QueryPanel from "../features/ask/components/QueryPanel.jsx";
import AnswerPanel from "../features/ask/components/AnswerPanel.jsx";
import ConfidenceBreakdown from "../features/retrieval-comparison/ConfidenceBreakdown.jsx";
import SourcesList from "../features/retrieval-comparison/SourcesList.jsx";
import { fetchHealth, fetchDocuments, ask, ingest } from "../lib/api.js";

export default function App() {
  const turnsEndRef = useRef(null);
  useEffect(() => { turnsEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [turns]);
  const [health, setHealth] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [totalChunks, setTotalChunks] = useState(0);

  const [question, setQuestion] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [chunkingStrategy, setChunkingStrategy] = useState("");
  const [compareDenseOnly, setCompareDenseOnly] = useState(false);

  const [loading, setLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [turns, setTurns] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [verifyCitations, setVerifyCitations] = useState(true);
  const [highlightedMarker, setHighlightedMarker] = useState(null);
  const highlightTimeout = useRef(null);

  async function refreshIndexState() {
    try {
      const [h, d] = await Promise.all([fetchHealth(), fetchDocuments()]);
      setHealth(h);
      setDocuments(d.source_documents);
      setTotalChunks(d.total_chunks);
    } catch {
      setHealth({ status: "unreachable" });
    }
  }

  useEffect(() => {
    refreshIndexState();
  }, []);

  async function handleUpload(files) {
    setIsUploading(true);
    setError(null);
    try {
      await ingest(files);
      await refreshIndexState();
    } catch (err) {
      setError(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  }

  async function handleAsk() {
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const data = await ask({
        question: question.trim(),
        conversationId,
        verifyCitations,
        chunkingStrategy: chunkingStrategy || null,
        compareDenseOnly,
        imageUrl: imageUrl.trim() || null,
      });
      setConversationId(data.conversation_id);
      setTurns([...turns, { question: question.trim(), result: data }]);
      setQuestion("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }
  
  function handleNewConversation() {
    setTurns([]);
    setConversationId(null);
    setQuestion("");
    setError(null);
  }

  function handleCiteClick(marker) {
    const el = document.getElementById(`source-hybrid-${marker}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlightedMarker(marker);
    clearTimeout(highlightTimeout.current);
    highlightTimeout.current = setTimeout(() => setHighlightedMarker(null), 1600);
  }

  const isHealthy = health?.status === "ok";

  return (
    <div className="shell">
      <div className="topbar">
        <div className="topbar__title">
          RAG QUERY CONSOLE
          <small>hybrid dense + BM25 retrieval</small>
        </div>
        <div className="topbar__meta">
          {health && (
            <span>
              <span className={`status-dot ${isHealthy ? "status-dot--ok" : "status-dot--down"}`} />
              {isHealthy ? `${health.embedding_provider} / ${health.llm_mode}` : "unreachable"}
            </span>
          )}
          {health?.reranker_provider && health.reranker_provider !== "none" && <span>rerank: {health.reranker_provider}</span>}
        </div>
      </div>

      <Sidebar 
        documents={documents} 
        totalChunks={totalChunks} 
        onUpload={handleUpload}
        isUploading={isUploading}
      />

      <main className="main">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
             <input type="checkbox" checked={verifyCitations} onChange={(e) => setVerifyCitations(e.target.checked)} />
             Verify Citations
          </label>
          <button onClick={handleNewConversation} className="btn">New Conversation</button>
        </div>
        
        <div className="turns-list" style={{ display: "flex", flexDirection: "column", gap: "2rem", marginBottom: "2rem" }}>
          {turns.length === 0 && !loading && !error && (
            <div className="empty-state">
              <strong>Nothing asked yet.</strong>
              Try a question about one of the {documents.length || "indexed"} documents on the left.
            </div>
          )}
          {turns.map((turn, i) => (
            <div key={i} className="turn" style={{ border: "1px solid var(--border)", padding: "1rem", borderRadius: "8px" }}>
              <div style={{ fontWeight: "bold", marginBottom: "1rem", color: "var(--fg-muted)" }}>Q: {turn.question}</div>
              <AnswerPanel result={turn.result} onCiteClick={handleCiteClick} />
              {i === turns.length - 1 && (
                <>
                  <ConfidenceBreakdown result={turn.result} />
                  <SourcesList
                    sources={turn.result.sources}
                    denseOnlySources={turn.result.dense_only_sources}
                    highlightedMarker={highlightedMarker}
                  />
                </>
              )}
            </div>
          ))}
          <div ref={turnsEndRef} />
        </div>

        {loading && <p className="loading-line">retrieving &amp; generating</p>}
        {error && <div className="error-banner">{error}</div>}

        <div style={{ position: "sticky", bottom: 0, backgroundColor: "var(--bg)", paddingBottom: "1rem" }}>
          <QueryPanel
            question={question}
            onQuestionChange={setQuestion}
            imageUrl={imageUrl}
            onImageUrlChange={setImageUrl}
            onSubmit={handleAsk}
            loading={loading}
            compareDenseOnly={compareDenseOnly}
            onToggleCompare={setCompareDenseOnly}
            chunkingStrategy={chunkingStrategy}
            onStrategyChange={setChunkingStrategy}
          />
        </div>
      </main>
    </div>
  );
}
