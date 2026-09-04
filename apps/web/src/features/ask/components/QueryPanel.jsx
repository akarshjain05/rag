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
        <div className="query-input-group">
          <label htmlFor="query-question" className="sr-only">Ask a question</label>
          <input
            id="query-question"
            className="query-input"
            type="text"
            placeholder="Ask something about the indexed documents…"
            value={question}
            onChange={(e) => onQuestionChange(e.target.value)}
            disabled={loading}
          />
          <label htmlFor="query-image" className="sr-only">Optional image URL</label>
          <input
            id="query-image"
            className="query-input query-image-input"
            type="text"
            placeholder="Optional image URL (e.g. for Moonshot vision models)..."
            value={imageUrl}
            onChange={(e) => onImageUrlChange(e.target.value)}
            disabled={loading}
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
