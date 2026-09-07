import re
with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

bad_set_conf1 = """              if (lastTurn.confidence_info) {
                setConfidenceInfo({
                  retrieval_confidence: lastTurn.confidence_info.retrieval,
                  citation_coverage: lastTurn.confidence_info.citation,
                  completeness: lastTurn.confidence_info.completeness,
                  composite_confidence: lastTurn.confidence_info.composite
                });"""
good_set_conf1 = """              if (lastTurn.confidence_info) {
                setConfidenceInfo({
                  retrieval_confidence: lastTurn.confidence_info.retrieval,
                  citation_coverage: lastTurn.confidence_info.citation,
                  completeness: lastTurn.confidence_info.completeness,
                  composite_confidence: lastTurn.confidence_info.composite,
                  mode: res.mode || 'standard'
                });"""
text = text.replace(bad_set_conf1, good_set_conf1)

bad_set_conf2 = """      setConfidenceInfo({
        composite: res.composite_confidence,
        retrieval: res.retrieval_confidence,
        completeness: res.completeness,
        coverage: res.citation_coverage
      });"""
good_set_conf2 = """      setConfidenceInfo({
        composite: res.composite_confidence,
        retrieval: res.retrieval_confidence,
        completeness: res.completeness,
        coverage: res.citation_coverage,
        mode: res.mode || 'standard'
      });"""
text = text.replace(bad_set_conf2, good_set_conf2)

bad_ui = """                    <div className={`inline-block px-2 py-0.5 border ${isHighConf ? 'border-success bg-success-tint text-success' : isLowConf ? 'border-danger bg-danger-tint text-danger' : 'border-warning bg-warning-tint text-warning'} font-mono text-[11px] uppercase tracking-widest -rotate-2`}>
                      {isHighConf ? 'Verified · High Confidence' : isLowConf ? 'Needs review · Low confidence' : 'Moderate confidence'}
                    </div>
                    <div className="font-mono text-[11px] text-ink-muted uppercase tracking-wider">
                      Composite Score: {confidenceInfo.composite?.toFixed(2) || 'N/A'}
                    </div>"""
                    
good_ui = """                    <div className={`inline-block px-2 py-0.5 border ${isHighConf ? 'border-success bg-success-tint text-success' : isLowConf ? 'border-danger bg-danger-tint text-danger' : 'border-warning bg-warning-tint text-warning'} font-mono text-[11px] uppercase tracking-widest -rotate-2`}>
                      {isHighConf ? 'Verified · High Confidence' : isLowConf ? 'Needs review · Low confidence' : 'Moderate confidence'}
                    </div>
                    {confidenceInfo.mode === 'expanded_query' && (
                       <div className="inline-block px-2 py-0.5 border border-accent bg-accent/10 text-accent font-mono text-[11px] uppercase tracking-widest">
                         ⚡ CRAG: Low confidence retrieval detected. Query expanded.
                       </div>
                    )}
                    <div className="font-mono text-[11px] text-ink-muted uppercase tracking-wider">
                      Composite Score: {confidenceInfo.composite?.toFixed(2) || 'N/A'}
                    </div>"""
text = text.replace(bad_ui, good_ui)

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)
