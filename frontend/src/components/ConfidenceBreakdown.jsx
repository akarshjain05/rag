function colorFor(value) {
  if (value === null || value === undefined) return "var(--ink-faint)";
  if (value >= 0.7) return "var(--accent-dense)";
  if (value >= 0.4) return "var(--accent-warn)";
  return "var(--accent-danger)";
}

function Meter({ label, value, basis, emphasize }) {
  const pct = value === null || value === undefined ? 0 : Math.round(value * 100);
  return (
    <div className={"meter" + (emphasize ? " meter--composite" : "")}>
      <div className="meter__label">{label}</div>
      <div className="meter__row">
        <div className="meter__track">
          <div className="meter__fill" style={{ width: `${pct}%`, background: colorFor(value) }} />
        </div>
        <div className="meter__value" style={{ color: colorFor(value) }}>
          {value === null || value === undefined ? "n/a" : value.toFixed(2)}
        </div>
      </div>
      {basis && <div className="meter__basis">basis: {basis}</div>}
    </div>
  );
}

export default function ConfidenceBreakdown({ result }) {
  if (!result) return null;
  const { retrieval_confidence, citation_coverage, citation_coverage_basis, completeness, composite_confidence } = result;

  return (
    <section className="confidence-panel">
      <p className="section-label">Confidence, by dimension</p>
      <div className="meter-grid">
        <Meter label="retrieval confidence" value={retrieval_confidence} />
        <Meter label="citation coverage" value={citation_coverage} basis={citation_coverage_basis} />
        <Meter label="answer completeness" value={completeness} />
        <Meter label="composite" value={composite_confidence} emphasize />
      </div>
    </section>
  );
}
