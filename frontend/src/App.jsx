import { useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import QueryPanel from "./components/QueryPanel.jsx";
import AnswerPanel from "./components/AnswerPanel.jsx";
import ConfidenceBreakdown from "./components/ConfidenceBreakdown.jsx";
import SourcesList from "./components/SourcesList.jsx";
import { fetchHealth, fetchDocuments, ask } from "./api.js";

export default function App() {
  const [health, setHealth] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [totalChunks, setTotalChunks] = useState(0);

  const [question, setQuestion] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [chunkingStrategy, setChunkingStrategy] = useState("");
  const [compareDenseOnly, setCompareDenseOnly] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
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

  async function handleAsk() {
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const data = await ask({
        question: question.trim(),
        chunkingStrategy: chunkingStrategy || null,
        compareDenseOnly,
        imageUrl: imageUrl.trim() || null,
      });
      setResult(data);
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
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

      <Sidebar documents={documents} totalChunks={totalChunks} />

      <main className="main">
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

        {loading && <p className="loading-line">retrieving &amp; generating</p>}
        {error && <div className="error-banner">{error}</div>}

        {!loading && !error && !result && (
          <div className="empty-state">
            <strong>Nothing asked yet.</strong>
            Try a question about one of the {documents.length || "indexed"} documents on the left — e.g. "how many
            vacation days do employees accrue per month?"
          </div>
        )}

        {result && (
          <>
            <AnswerPanel result={result} onCiteClick={handleCiteClick} />
            <ConfidenceBreakdown result={result} />
            <SourcesList
              sources={result.sources}
              denseOnlySources={result.dense_only_sources}
              highlightedMarker={highlightedMarker}
            />
          </>
        )}
      </main>
    </div>
  );
}
