import re
with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

bad_state = """  const [compareDenseOnly, setCompareDenseOnly] = React.useState(false);"""
good_state = """  const [compareDenseOnly, setCompareDenseOnly] = React.useState(false);
  const abortControllerRef = React.useRef<AbortController | null>(null);
  
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };"""
text = text.replace(bad_state, good_state)


bad_ask = """  const handleAsk = async () => {
    if (!query.trim() || loading) return;
    const q = query;
    setQuery("");
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    
    try {
      const { ask } = await import('./lib/api');
      const res = await ask({ question: q, conversationId, verifyCitations: true, compareDenseOnly });
      
      const newAssistantMsg = { role: 'assistant', content: res.answer, feedback: null };"""
good_ask = """  const handleAsk = async () => {
    if (!query.trim() || loading) return;
    const q = query;
    setQuery("");
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    
    abortControllerRef.current = new AbortController();
    
    try {
      const { ask } = await import('./lib/api');
      const res = await ask({ 
        signal: abortControllerRef.current.signal,
        question: q, 
        conversationId, 
        verifyCitations: true, 
        compareDenseOnly 
      });
      
      const newAssistantMsg = { role: 'assistant', content: res.answer, feedback: null };"""
text = text.replace(bad_ask, good_ask)


bad_catch = """      }
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error: ' + e.message }]);
    } finally {
      setLoading(false);
    }
  };"""
good_catch = """      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        // Just remove the user's question from the UI if they aborted before the backend answered
        setMessages(prev => prev.slice(0, -1));
      } else {
        console.error(e);
        setMessages(prev => [...prev, { role: 'assistant', content: 'Error: ' + (e.message || 'Unknown error') }]);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };"""
text = text.replace(bad_catch, good_catch)


bad_ui = """        {loading && (
           <div className="mt-4 flex flex-col gap-1 w-32">
              <span className="text-[11px] font-mono uppercase tracking-[0.05em] text-ink-muted">Analyzing...</span>
              <div className="h-[1px] bg-border w-full overflow-hidden">
                <div className="h-full bg-accent animate-[loading-rule_1.5s_ease-in-out_infinite]" style={{ transformOrigin: 'left' }}></div>
              </div>
           </div>
        )}"""
good_ui = """        {loading && (
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
        )}"""
text = text.replace(bad_ui, good_ui)

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)
