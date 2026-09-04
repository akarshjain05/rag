import { useEffect, useRef, useState } from "react";
import Sidebar from "../features/documents/Sidebar.jsx";
import QueryPanel from "../features/ask/components/QueryPanel.jsx";
import AnswerPanel from "../features/ask/components/AnswerPanel.jsx";
import ConfidenceBreakdown from "../features/retrieval-comparison/ConfidenceBreakdown.jsx";
import SourcesList from "../features/retrieval-comparison/SourcesList.jsx";
import { fetchHealth, fetchDocuments, ask, ingest, deleteDocument } from "../lib/api.js";

export default function App() {
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
  const currentAskController = useRef(null);
  const turnsEndRef = useRef(null);
  useEffect(() => { turnsEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [turns]);

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

  async function handleDeleteDocument(sourceDocument) {
    if (!window.confirm(`Are you sure you want to delete "${sourceDocument}"?`)) return;
    try {
      await deleteDocument(sourceDocument);
      loadDocs(); // refresh list
    } catch (err) {
      alert(`Error deleting document: ${err.message}`);
    }
  }

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
    const currentQuestion = question.trim();
    if (!currentQuestion || loading) return;
    
    if (currentAskController.current) {
      currentAskController.current.abort();
    }
    const controller = new AbortController();
    currentAskController.current = controller;

    setLoading(true);
    setError(null);
    try {
      const data = await ask({ signal: controller.signal,
        question: currentQuestion,
        conversationId,
        verifyCitations,
        chunkingStrategy: chunkingStrategy || null,
        compareDenseOnly,
        imageUrl: imageUrl.trim() || null,
      });
      setConversationId(data.conversation_id);
      setTurns(prev => [...prev, { question: currentQuestion, result: data }]);
      setQuestion("");
    
    } catch (err) {
      if (err.name === 'AbortError') return;
      setError(err.message);
    } finally {
      if (currentAskController.current === controller) {
        setLoading(false);
      }
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
        onDeleteDocument={handleDeleteDocument}
      />

      <main className="main">
        <div className="app-header">
          <label className="app-header-label">
             <input type="checkbox" checked={verifyCitations} onChange={(e) => setVerifyCitations(e.target.checked)} />
             Verify Citations
          </label>
          <button onClick={handleNewConversation} className="ask-button">New Conversation</button>
        </div>
        
        <div className="turns-list" >
          {turns.length === 0 && !loading && !error && (
            <div className="empty-state">
              <strong>Nothing asked yet.</strong>
              Try a question about one of the {documents.length || "indexed"} documents on the left.
            </div>
          )}
          {turns.map((turn, i) => (
            <div key={i} className="turn" >
              <div className="turn-question">Q: {turn.question}</div>
              
              <AnswerPanel result={turn.result} onCiteClick={handleCiteClick} />
              
              <details className="turn-details" open={i === turns.length - 1}>
                <summary className="turn-details-summary">Retrieval Details</summary>
                <div className="turn-details-content">
                  <ConfidenceBreakdown result={turn.result} />
                  <SourcesList 
                    sources={turn.result.sources}
                    denseOnlySources={turn.result.dense_only_sources}
                    highlightedMarker={highlightedMarker}
                    compareDenseOnly={compareDenseOnly}
                  />
                </div>
              </details>

            </div>
          ))}
          <div ref={turnsEndRef} />
        </div>

        <div aria-live="polite" aria-atomic="true">
          {loading && <p className="loading-line">retrieving &amp; generating</p>}
          {error && <div className="error-banner">{error}</div>}
        </div>

        <div className="sticky-query">
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
