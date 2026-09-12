// @ts-nocheck
// @ts-nocheck

import { createPortal } from "react-dom";

import React, { useState, useEffect } from 'react';
import { fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from '../lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbsUp, ThumbsDown, LogOut, Moon, Sun, Menu, MoreHorizontal, Copy } from 'lucide-react';




export default function ChatView({ conversationId, setConversationId, setMobileMenuOpen, onNewMessage }) {

  const renderContentWithCitations = (text: string) => {
    if (!text) return null;
    const regex = /([^.!?\n]+[.!?]?\s*)(\[\d+\])/g;
    let lastIndex = 0;
    const result = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        result.push(text.substring(lastIndex, match.index));
      }
      const phrase = match[1];
      const citeMatch = match[2].match(/\[(\d+)\]/);
      const citeNum = citeMatch ? citeMatch[1] : '';
      result.push(
        <span key={match.index} className="inline group">
          {phrase}
          <span>
            <sup className="text-accent font-mono ml-[2px]">{citeNum}</sup>
          </span>
        </span>
      );
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      result.push(text.substring(lastIndex));
    }
    return result.length > 0 ? result : text;
  };

  const [query, setQuery] = React.useState("");
  const [messages, setMessages] = React.useState<any[]>([]);
  const [sources, setSources] = React.useState<any[]>([]);
  const [denseOnlySources, setDenseOnlySources] = React.useState<any[]>([]);
  const [usedMarkers, setUsedMarkers] = React.useState<number[]>([]);
  const [unsupportedMarkers, setUnsupportedMarkers] = React.useState<number[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [activeCitation, setActiveCitation] = React.useState<number | null>(null);
  const [confidenceInfo, setConfidenceInfo] = React.useState<any>(null);

  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [messages, sources, loading]);

  const [compareDenseOnly, setCompareDenseOnly] = React.useState(false);
  const [copiedIndex, setCopiedIndex] = React.useState<number | null>(null);

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };
  const abortControllerRef = React.useRef<AbortController | null>(null);
  
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };
  const isInitialMount = React.useRef(true);
  const skipFetch = React.useRef(false);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [query]);

  React.useEffect(() => {
    if (skipFetch.current) {
      skipFetch.current = false;
      return;
    }
    if (conversationId) {
      import('../lib/api').then(({ fetchConversation }) => {
        fetchConversation(conversationId).then(res => {
          setDenseOnlySources([]);
          if (res.history) {
            const mapped = [];
            res.history.forEach(t => {
              mapped.push({ role: 'user', content: t.user });
              mapped.push({ role: 'assistant', content: t.assistant });
            });
            setMessages(mapped);
            
            // Restore sources and confidence from the very last turn
            if (res.history.length > 0) {
              const lastTurn = res.history[res.history.length - 1];
              if (lastTurn.sources) {
                setSources(lastTurn.sources);
              } else {
                setSources([]);
              }
              if (lastTurn.confidence_info) {
                setConfidenceInfo({
                  retrieval: lastTurn.confidence_info.retrieval,
                  coverage: lastTurn.confidence_info.citation,
                  completeness: lastTurn.confidence_info.completeness,
                  composite: lastTurn.confidence_info.composite,
                  mode: res.mode || 'standard'
                });
              } else {
                setConfidenceInfo(null);
              }
            } else {
              // If history is empty, clear stale state
              setSources([]);
              setConfidenceInfo(null);
            }
          }
        }).catch(err => {
          console.error(err);
          setMessages([{ role: 'assistant', content: 'Error loading conversation history.' }]);
          setSources([]);
          setConfidenceInfo(null);
        });
      });
    } else {
      setMessages([]);
      setSources([]);
      setConfidenceInfo(null);
    }
  }, [conversationId]);

  const handleAsk = async () => {
    if (!query.trim() || loading) return;
    const q = query;
    setQuery("");
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    
    // Clear previous interaction metadata
    setSources([]);
    setDenseOnlySources([]);
    setUsedMarkers([]);
    setUnsupportedMarkers([]);
    setConfidenceInfo(null);
    
    setLoading(true);
    
    let cid = conversationId;
    if (!cid) {
      cid = crypto.randomUUID();
      skipFetch.current = true;
      setConversationId(cid);
    }
    
    try {
      abortControllerRef.current = new AbortController();
      const { ask } = await import('../lib/api');
      const res = await ask({ 
        signal: abortControllerRef.current.signal,
        question: q, 
        conversationId: cid, 
        verifyCitations: true, 
        compareDenseOnly 
      });
      
      if (onNewMessage) onNewMessage();

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: res.answer, markers: res.used_citation_markers || [] }
      ]);
      setSources(res.sources || []);
      setDenseOnlySources(res.dense_only_sources || []);
      setUsedMarkers(res.used_citation_markers || []);
      setUnsupportedMarkers(res.unsupported_citation_markers || []);
      setConfidenceInfo({
        composite: res.composite_confidence,
        retrieval: res.retrieval_confidence,
        completeness: res.completeness,
        coverage: res.citation_coverage,
        mode: res.mode || 'standard'
      });
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setMessages(prev => [...prev, { role: 'assistant', content: '[Discarded — type "continue" to resume this question]' }]);
        // Keep the same conversationId. Nothing was persisted server-side for
        // the stopped turn either way, so history is still genuinely empty --
        // but preserving the id lets the backend recognize an immediate
        // "continue" as a request to resume this exact question instead of
        // starting a second, disconnected conversation.
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: "Error: " + err.message }]);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleFeedback = async (idx, isHelpful) => {
    if (!conversationId) return;
    const { submitFeedback } = await import('../lib/api');
    
    // Calculate the turn index (assistant messages only)
    const turnIndex = Math.floor(idx / 2);
    
    // Determine if we are toggling off an already active feedback
    const currentFeedback = messages[idx].feedback;
    const newFeedback = currentFeedback === isHelpful ? null : isHelpful;
    
    try {
      await submitFeedback(conversationId, turnIndex, newFeedback);
      setMessages(prev => {
        const next = [...prev];
        next[idx] = { ...next[idx], feedback: newFeedback };
        return next;
      });
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

  const handleExport = () => {
    if (!messages.length) return;
    let md = `# Conversation\n\n`;
    messages.forEach(m => {
      md += `**${m.role === 'user' ? 'User' : 'Assistant'}**:\n${m.content}\n\n`;
      if (m.markers && m.markers.length > 0) {
        md += `*Sources*: ${m.markers.join(', ')}\n\n`;
      }
    });
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conversation_${conversationId || 'export'}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const compScore = confidenceInfo?.composite || 0;
  const isHighConf = compScore > 0.8;
  const isLowConf = compScore < 0.4;

  return (
    <div className="flex-1 bg-surface relative flex flex-col justify-between h-full overflow-hidden min-h-0">
      
      {/* Content Region: Answer & Citations */}
      <div className="flex-1 overflow-y-auto px-6 md:px-12 pt-8 pb-6 w-full flex flex-col gap-10 min-h-0">
        <div className="max-w-4xl w-full mx-auto flex flex-col gap-10">

        {(messages || []).map((m, i) => (
           <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end mb-6' : 'items-start mb-10'}`}>
              
              {m.role === 'assistant' && i === messages.length - 1 && confidenceInfo && (
                <details className="mb-6 group/details">
                  <summary className="flex items-center gap-4 cursor-pointer list-none">
                    <div className={`inline-block px-2 py-0.5 border ${isHighConf ? 'border-success bg-success-tint text-success' : isLowConf ? 'border-danger bg-danger-tint text-danger' : 'border-warning bg-warning-tint text-warning'} font-mono text-[11px] uppercase tracking-widest`}>
                      {isHighConf ? 'Verified · High Confidence' : isLowConf ? 'Needs review · Low confidence' : 'Moderate confidence'}
                    </div>
                    {confidenceInfo.mode === 'expanded_query' && (
                       <div className="inline-block px-2 py-0.5 border border-accent bg-accent/10 text-accent font-mono text-[11px] uppercase tracking-widest">
                         ⚡ CRAG: Low confidence retrieval detected. Query expanded.
                       </div>
                    )}
                    <div className="font-mono text-[11px] text-ink-muted uppercase tracking-wider">
                      Composite Score: {confidenceInfo.composite?.toFixed(2) || 'N/A'}
                    </div>
                  </summary>
                  <div className="mt-4 p-4 bg-surface-card border border-border flex gap-6 text-ink font-mono text-[11px]">
                    <span className="flex flex-col">
                      <span className="text-ink-muted mb-1">RETRIEVAL</span>
                      <span>{confidenceInfo.retrieval?.toFixed(2) || 'N/A'}</span>
                    </span>
                    <span className="flex flex-col">
                      <span className="text-ink-muted mb-1">CITATIONS</span>
                      <span>{confidenceInfo.coverage?.toFixed(2) || 'N/A'}</span>
                    </span>
                    <span className="flex flex-col">
                      <span className="text-ink-muted mb-1">COMPLETENESS</span>
                      <span>{confidenceInfo.completeness?.toFixed(2) || 'N/A'}</span>
                    </span>
                  </div>
                </details>
              )}

              <div className="relative group/message">
                <div className={`${m.role === 'user' ? 'bg-surface-card border border-border px-4 py-3 rounded-none text-[14px] font-sans' : 'font-serif text-[16px] leading-[1.75] text-ink'} max-w-full whitespace-pre-wrap`}>
                   {m.role === 'assistant' ? renderContentWithCitations(m.content) : m.content}
                </div>
                {m.role === 'user' && (
                  <div className="flex justify-end mt-2 text-ink-muted opacity-0 group-hover/message:opacity-100 transition-opacity">
                    <button 
                      onClick={() => handleCopy(m.content, i)}
                      className="hover:text-ink transition-colors cursor-default"
                      title="Copy text"
                    >
                      <Copy size={14} />
                    </button>
                  </div>
                )}
              </div>

              {m.role === 'assistant' && (
                <div className="flex items-center gap-4 mt-3 text-ink-muted">
                  <button 
                    onClick={() => handleCopy(m.content, i)}
                    className="hover:text-ink transition-colors"
                    title="Copy text"
                  >
                    <Copy size={14} />
                  </button>
                  <button 
                    onClick={() => handleFeedback(i, true)}
                    className={`hover:text-success transition-colors ${m.feedback === true ? 'text-success' : ''}`}
                    title="Helpful"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"/></svg>
                  </button>
                  <button 
                    onClick={() => handleFeedback(i, false)}
                    className={`hover:text-danger transition-colors ${m.feedback === false ? 'text-danger' : ''}`}
                    title="Unhelpful"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z"/></svg>
                  </button>
                </div>
              )}
           </div>
        ))}

        {loading && (
           <div className="mt-4 flex items-center gap-4">
             <div className="flex flex-col gap-1 w-32">
                <span className="text-[11px] font-mono uppercase tracking-[0.05em] text-ink-muted">Analyzing...</span>
                <div className="h-[1px] bg-border w-full overflow-hidden">
                  <div className="h-full bg-accent animate-[loading-rule_1.5s_ease-in-out_infinite]" style={{ transformOrigin: 'left' }}></div>
                </div>
             </div>
             <button 
               onClick={handleStop} 
               className="text-[10px] uppercase font-mono tracking-widest text-ink-muted hover:text-danger flex items-center gap-1 px-2 py-1 transition-colors"
             >
               <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>
               Stop
             </button>
           </div>
        )}

        {/* Sources Section */}
        {sources.length > 0 && (
           <details className="pt-8 border-t border-border group/sources">
             <summary className="font-sans text-[13px] text-ink-secondary mb-4 uppercase tracking-wider cursor-pointer list-none flex items-center gap-2 hover:text-ink transition-colors">
               <span>Sources ({sources.length})</span>
               <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform group-open/sources:rotate-180"><path d="m6 9 6 6 6-6"/></svg>
             </summary>
             
             <div className="flex flex-col gap-4">
               {(sources || []).map((s, i) => (
                 <div key={i} className="bg-surface-card border border-border border-t-[3px] border-t-accent p-4 flex flex-col gap-3 transition-colors hover:border-b-accent hover:border-l-accent hover:border-r-accent">
                    <div className="flex items-baseline justify-between">
                      <div className="flex items-center gap-3 truncate">
                        <span className="font-mono text-[12px] text-ink"><sup className="text-accent mr-0.5">{s.marker}</sup>{s.source_document}</span>
                        {s.section_heading && <span className="font-serif italic text-[13px] text-ink-muted truncate">{s.section_heading}</span>}
                      </div>
                      {s.chunk_id && <span className="font-mono text-[11px] text-ink-muted shrink-0 ml-4 hidden sm:block">CHUNK ID: {s.chunk_id.substring(0, 12)}</span>}
                    </div>
                    <div className="font-serif text-[15px] leading-relaxed text-ink-secondary border-l-2 border-border-strong pl-4 italic line-clamp-4">
                      "{s.text}"
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <div className="text-[9px] flex gap-3 font-mono text-ink-secondary tracking-[0.05em] uppercase">
                        <span title="Dense Score">D: {s.dense_score?.toFixed(2) || '-'}</span>
                        {!compareDenseOnly && <span title="Sparse Score">S: {s.sparse_score?.toFixed(2) || '-'}</span>}
                        <span title="Rerank Score">R: {s.rerank_score?.toFixed(2) || '-'}</span>
                      </div>
                      {usedMarkers.includes(s.marker) ? (
                        unsupportedMarkers.includes(s.marker) ? (
                          <span className="inline-block px-2 py-0.5 border border-danger bg-danger-tint text-danger font-mono text-[10px] uppercase tracking-wider">
                            Unsupported
                          </span>
                        ) : (
                          <span className="inline-block px-2 py-0.5 border border-success bg-success-tint text-success font-mono text-[10px] uppercase tracking-wider">
                            Supported
                          </span>
                        )
                      ) : null}
                    </div>
                 </div>
               ))}
             </div>
           </details>
        )}
        
        {compareDenseOnly && denseOnlySources.length > 0 && (
           <details className="pt-8 border-t border-border group/dense-sources">
             <summary className="font-sans text-[13px] text-ink-secondary mb-4 uppercase tracking-wider cursor-pointer list-none flex items-center gap-2 hover:text-ink transition-colors">
               <span>Dense-only comparison ({denseOnlySources.length})</span>
               <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="transition-transform group-open/dense-sources:rotate-180"><path d="m6 9 6 6 6-6"/></svg>
             </summary>
             <p className="text-[12px] text-ink-muted mb-4 font-sans">
               What plain dense-vector search alone would have retrieved -- no sparse/BM25, no reranking. Compare against Sources above.
             </p>
             <div className="flex flex-col gap-4">
               {(denseOnlySources || []).map((s, i) => (
                 <div key={i} className="bg-surface-card border border-border border-t-[3px] border-t-ink-muted p-4 flex flex-col gap-3">
                    <div className="flex items-baseline justify-between">
                      <span className="font-mono text-[12px] text-ink">{s.source_document}</span>
                      {s.dense_rank && <span className="font-mono text-[11px] text-ink-muted">DENSE RANK: {s.dense_rank}</span>}
                    </div>
                    <div className="font-serif text-[15px] leading-relaxed text-ink-secondary border-l-2 border-border-strong pl-4 italic line-clamp-4">
                      "{s.text}"
                    </div>
                 </div>
               ))}
             </div>
           </details>
        )}
        <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Bottom Header / Input Area */}
      <footer className="mt-auto px-6 md:px-12 py-6 max-w-4xl w-full mx-auto shrink-0 bg-surface">
        <div className="relative border-b border-border-strong pb-2 flex items-end">
          <textarea 
            ref={textareaRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
            placeholder="Ask the archive..." 
            className="flex-1 bg-transparent border-none font-serif italic text-[18px] placeholder:text-ink-muted text-ink focus:outline-none focus:ring-0 resize-none overflow-y-auto max-h-[200px] py-0"
            rows={1}
            disabled={loading}
          />
          <button 
            onClick={handleAsk}
            disabled={loading || !query.trim()}
            className="ml-4 px-4 py-1 border border-accent text-accent font-sans text-[13px] hover:bg-accent-tint transition-colors disabled:opacity-50 disabled:hover:bg-transparent"
          >
            Ask
          </button>
        </div>
        <div className="flex gap-2 items-center mt-3">
           <label className="flex items-center gap-2 text-[11px] font-mono text-ink-secondary cursor-pointer uppercase tracking-wider">
             <input type="checkbox" checked={compareDenseOnly} onChange={e => setCompareDenseOnly(e.target.checked)} className="rounded-none border-border accent-accent" />
             Dense-only mode
           </label>
        </div>
      </footer>
    </div>
  );
}
