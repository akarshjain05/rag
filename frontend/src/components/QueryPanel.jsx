const STRATEGIES = [
  { value: "", label: "server default" },
  { value: "fixed_size", label: "fixed_size" },
  { value: "structure_aware", label: "structure_aware" },
  { value: "semantic", label: "semantic" },
];

export default function QueryPanel({
  question,
  onQuestionChange,
  imageUrl,
  onImageUrlChange,
  onSubmit,
  loading,
  compareDenseOnly,
  onToggleCompare,
  chunkingStrategy,
  onStrategyChange,
}) {
  return (
    <>
      <form
        className="query-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, gap: "8px" }}>
          <input
            className="query-input"
            type="text"
            placeholder="Ask something about the indexed documents…"
            value={question}
            onChange={(e) => onQuestionChange(e.target.value)}
            disabled={loading}
          />
          <input
            className="query-input"
            type="text"
            placeholder="Optional image URL (e.g. for Moonshot vision models)..."
            value={imageUrl}
            onChange={(e) => onImageUrlChange(e.target.value)}
            disabled={loading}
            style={{ fontSize: "0.9em", padding: "8px 12px" }}
          />
        </div>
        <button className="ask-button" type="submit" disabled={loading || !question.trim()}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>

      <div className="controls-row">
        <label className="toggle">
          <input type="checkbox" checked={compareDenseOnly} onChange={(e) => onToggleCompare(e.target.checked)} />
          compare hybrid vs. dense-only
        </label>

        <select
          className="strategy-select"
          value={chunkingStrategy}
          onChange={(e) => onStrategyChange(e.target.value)}
          title="Chunking strategy filter"
        >
          {STRATEGIES.map((s) => (
            <option key={s.value} value={s.value}>
              strategy: {s.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
