function SourceCard({ source, idPrefix, highlighted }) {
  const meta = [];
  if (source.section_heading) meta.push(source.section_heading);
  if (source.page_number !== null && source.page_number !== undefined) meta.push(`page ${source.page_number}`);

  return (
    <div id={`${idPrefix}-${source.marker}`} className={"source-card" + (highlighted ? " source-card--highlight" : "")}>
      <span className="source-card__marker">[{source.marker}]</span>
      <div className="source-card__body">
        <div className="source-card__doc">{source.source_document || "unknown"}</div>
        {meta.length > 0 && <div className="source-card__meta">{meta.join(" · ")}</div>}
      </div>
      <div className="source-card__ranks">
        {source.dense_rank != null && <span className="rank-chip rank-chip--dense">dense #{source.dense_rank}</span>}
        {source.sparse_rank != null && <span className="rank-chip rank-chip--sparse">sparse #{source.sparse_rank}</span>}
        {source.rerank_score != null && (
          <span className="rank-chip rank-chip--rerank">rerank {source.rerank_score.toFixed(2)}</span>
        )}
      </div>
    </div>
  );
}

export default function SourcesList({ sources, denseOnlySources, highlightedMarker }) {
  if (!sources || sources.length === 0) return null;

  const comparing = Array.isArray(denseOnlySources);

  return (
    <section className="sources-panel">
      <p className="section-label">Retrieved sources, ranked</p>
      {comparing ? (
        <div className="source-columns">
          <div>
            <div className="source-column__header">
              <span className="method-tag method-tag--hybrid">HYBRID</span>
              <span style={{ fontSize: 11, color: "var(--ink-faint)" }}>used to generate the answer</span>
            </div>
            {sources.map((s) => (
              <SourceCard key={s.marker} source={s} idPrefix="source-hybrid" highlighted={highlightedMarker === s.marker} />
            ))}
          </div>
          <div>
            <div className="source-column__header">
              <span className="method-tag method-tag--dense">DENSE-ONLY</span>
              <span style={{ fontSize: 11, color: "var(--ink-faint)" }}>same query, no sparse/fusion</span>
            </div>
            {denseOnlySources.length === 0 ? (
              <p style={{ color: "var(--ink-faint)", fontSize: 13 }}>no results</p>
            ) : (
              denseOnlySources.map((s) => <SourceCard key={s.marker} source={s} idPrefix="source-dense" />)
            )}
          </div>
        </div>
      ) : (
        sources.map((s) => (
          <SourceCard key={s.marker} source={s} idPrefix="source-hybrid" highlighted={highlightedMarker === s.marker} />
        ))
      )}
    </section>
  );
}
