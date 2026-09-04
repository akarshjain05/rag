const MODE_LABELS = {
  llm: "generated",
  extractive: "extractive (no LLM)",
  low_confidence: "low confidence — declined",
  no_context: "no matching context",
};

// Splits "...accrues monthly [1]. Remote work needs approval [2]." into
// alternating text/citation segments so each [N] can be rendered as its
// own clickable element instead of dead text.
export function splitOnCitations(text) {
  const parts = [];
  const re = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "citation", value: Number(match[1]) });
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex) });
  }
  return parts;
}

export default function AnswerPanel({ result, onCiteClick }) {
  if (!result) return null;

  const { answer, mode, invalid_citation_markers, unsupported_citation_markers } = result;
  const invalidSet = new Set(invalid_citation_markers || []);
  const unsupportedSet = new Set(unsupported_citation_markers || []);
  const segments = splitOnCitations(answer);

  return (
    <section className="answer-panel">
      <p className="section-label">Answer</p>
      <span className={`answer-mode answer-mode--${mode}`}>{MODE_LABELS[mode] || mode}</span>
      <p className="answer-text">
        {segments.map((seg, i) =>
          seg.type === "text" ? (
            <span key={i}>{seg.value}</span>
          ) : (
            <button
              key={i}
              className={
                "citation-mark" +
                (invalidSet.has(seg.value) ? " citation-mark--invalid" : "") +
                (unsupportedSet.has(seg.value) ? " citation-mark--unsupported" : "")
              }
              aria-label={`Citation ${seg.value}`}
              title={
                invalidSet.has(seg.value)
                  ? "This citation number doesn't match any retrieved source"
                  : unsupportedSet.has(seg.value)
                  ? "A judge flagged this citation as not actually supporting the claim"
                  : "Jump to source"
              }
              onClick={() => onCiteClick(seg.value)}
            >
              [{seg.value}]
            </button>
          )
        )}
      </p>

      {(invalid_citation_markers?.length > 0 || unsupported_citation_markers?.length > 0) && (
        <p className="citation-flags">
          {invalid_citation_markers?.length > 0 && <>⚠ invalid citation(s): {invalid_citation_markers.join(", ")} &nbsp;</>}
          {unsupported_citation_markers?.length > 0 && <>⚠ unsupported citation(s): {unsupported_citation_markers.join(", ")}</>}
        </p>
      )}
    </section>
  );
}
