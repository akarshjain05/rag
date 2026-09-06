import React, { useState, useEffect } from 'react';
import { ask, fetchDocuments, ingest } from './lib/api';
import { Search, Mic, Activity, Layers, Hexagon, Scale, ShieldCheck, AlertTriangle, X, Trash2, Copy, MessageSquarePlus, Check } from 'lucide-react';
import { deleteDocument } from './lib/api';


class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 20, color: 'white', background: 'red' }}>
          <h1>Something went wrong.</h1>
          <pre>{String(this.state.error)}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return <ErrorBoundary><AppContent /></ErrorBoundary>;
}

function AppContent() {
  const [query, setQuery] = useState('');
  const [isDebateMode, setIsDebateMode] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string>("UPLOADING...");
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

  const [documents, setDocuments] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [lastQuery, setLastQuery] = useState('');
  const [conversationId] = useState(() => Math.random().toString(36).substring(2, 15));
  const [strictMode, setStrictMode] = useState(false);
  const [answerDetails, setAnswerDetails] = useState<any>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [copied, setCopied] = useState(false);


  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recognition, setRecognition] = useState<any>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        const rec = new SpeechRecognition();
        rec.continuous = true;
        rec.interimResults = true;
        
        rec.onresult = (event: any) => {
          let finalTranscript = '';
          for (let i = 0; i < event.results.length; i++) {
            finalTranscript += event.results[i][0].transcript;
          }
          setQuery(finalTranscript);
        };
        
        rec.onerror = (event: any) => {
          console.error("Speech recognition error", event.error);
          setIsRecording(false);
        };
        
        rec.onend = () => {
          setIsRecording(false);
        };
        
        setRecognition(rec);
      }
    }
  }, []);

  const toggleRecording = () => {
    if (isRecording) {
      recognition?.stop();
      setIsRecording(false);
    } else {
      setQuery(''); // Clear before new recording
      recognition?.start();
      setIsRecording(true);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // If user holds space and is not typing in the input box
      if (e.code === 'Space' && document.activeElement?.tagName !== 'INPUT' && !isRecording && recognition) {
        e.preventDefault();
        setQuery('');
        recognition.start();
        setIsRecording(true);
      }
    };
    
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && isRecording && recognition) {
        recognition.stop();
        setIsRecording(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [isRecording, recognition]);
  
  useEffect(() => {
    fetchDocuments().then(res => setDocuments(res.source_documents || [])).catch(console.error);
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setIsSearching(true);
    setLastQuery(query);
    
    // Cache the query for the API call and clear the input field
    const currentQuery = query;
    setQuery('');
    
    try {
      const res = await ask({ question: currentQuery, conversationId, verifyCitations: strictMode });
      setAnswer(res.answer);
      setSources(res.sources || []);
      setAnswerDetails(res);
    } catch (e) {
      console.error(e);
      setAnswer("Error fetching answer.");
    } finally {
      setIsSearching(false);
    }
  };
  
  const handleUpload = async (e) => {
    if (e.target.files?.length) {
      const controller = new AbortController();
      setAbortController(controller);
      try {
        setUploadProgress(0);
        setUploadMessage("UPLOADING...");
        await ingest(e.target.files, (pct, msg) => {
          setUploadProgress(pct);
          if (msg) setUploadMessage(msg.toUpperCase());
        }, controller.signal);
        const res = await fetchDocuments();
        setDocuments(res.source_documents || []);
      } catch (err) {
        if (err.name === "AbortError" || err.message === "Aborted") {
            console.log("Upload cancelled by user");
        } else {
            console.error("Upload failed:", err);
            alert("Upload failed: " + (err.message || String(err)));
        }
      } finally {
        setUploadProgress(null);
        setAbortController(null);
        e.target.value = null;
      }
    }
  };
  
  const handleCancelUpload = () => {
    if (abortController) {
      abortController.abort();
      setUploadProgress(null);
      setUploadMessage("CANCELLING...");
    }
  };
  
  const handleDeleteDoc = async (docName) => {
    if (confirm(`Are you sure you want to delete ${docName}?`)) {
      try {
        await deleteDocument(docName);
        const res = await fetchDocuments();
        setDocuments(res.source_documents || []);
      } catch(err) {
        alert("Failed to delete document: " + err.message);
      }
    }
  };
  
  const clearChat = () => {
    setQuery("");
    setAnswerDetails(null);
    setAnswer("");
    setSources([]);
    setLastQuery("");
  };
  
  const copyAnswer = () => {
    navigator.clipboard.writeText(answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };



  // Mock data for the holographic modal
  const citationData = {
    1: {
      doc: "handbook.md",
      title: "Vacation Policy",
      text: "All full-time employees are eligible for paid time off. Employees accrue vacation at a rate of 1.5 days per month, starting from their first full month of employment. Time off must be requested at least two weeks in advance. Unused vacation days do not roll over to the next calendar year.",
      highlight: "Employees accrue vacation at a rate of 1.5 days per month",
      confidence: 0.94,
      status: "verified" // verified | hallucinated
    }
  };

  return (
    <div className="flex h-screen w-full bg-[#0A0A0A] text-white overflow-hidden font-sans relative">
      
      {/* Left Sidebar: Document Minimaps */}
      <aside className="w-64 glass-panel border-r border-white/10 flex flex-col z-10 relative">
        <div className="p-4 border-b border-white/10 flex items-center gap-2">
          <Hexagon className="text-[#00F0FF] w-5 h-5" />
          <h1 className="font-mono text-sm tracking-widest font-bold">OMNISCIENT</h1>
        </div>
        
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-6">
          <h2 className="text-xs uppercase text-white/50 font-mono tracking-wider">Corpus Heatmap</h2>
          
          
          {documents.map((doc, idx) => (
            <div key={idx} className="flex flex-col gap-2 group cursor-pointer">
              <div className="flex justify-between items-end font-mono text-[10px]">
                <span className="text-white/70 group-hover:text-white transition-colors truncate w-3/4">{doc}</span>
                <div className="flex items-center gap-2">
                  <button onClick={async (e) => {
                    e.stopPropagation();
                    if(confirm('Delete ' + doc + '?')) {
                      await deleteDocument(doc);
                      fetchDocuments().then(res => setDocuments(res.source_documents || []));
                    }
                  }} className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-400 transition-opacity">
                    ✕
                  </button>
                  <span className="text-[#00F0FF]">DOC</span>
                </div>
              </div>
              <div className="h-8 w-full bg-white/5 rounded-sm flex overflow-hidden relative border border-white/5">
                {/* Generate pseudo-random organic chunks */}
                {Array.from({ length: 8 }).map((_, i) => {
                  const isHot = (doc.length + i) % 3 === 0;
                  const isWarm = (doc.length + i) % 5 === 0;
                  const width = 10 + ((doc.length * i) % 15) + '%';
                  
                  if (isHot) {
                    return <div key={i} style={{ width }} className="h-full bg-[#00F0FF]/60 shadow-[0_0_10px_#00F0FF]"></div>;
                  } else if (isWarm) {
                    return <div key={i} style={{ width }} className="h-full bg-[#00F0FF]/20"></div>;
                  } else {
                    return <div key={i} style={{ width }} className="h-full bg-transparent border-r border-white/5"></div>;
                  }
                })}
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 bg-gradient-to-t from-[#00F0FF]/10 to-transparent transition-opacity pointer-events-none"></div>
              </div>
            </div>
          ))}
          <div className="mt-4">
            {uploadProgress !== null ? (
              <div className="flex items-center gap-3">
                <div className="relative w-8 h-8 shrink-0">
                  <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                    <circle cx="18" cy="18" r="16" fill="none" className="stroke-white/10" strokeWidth="3"></circle>
                    <circle cx="18" cy="18" r="16" fill="none" className={uploadProgress > 100 ? "stroke-[#00F0FF] animate-spin origin-center" : "stroke-[#00F0FF] transition-all duration-300"} strokeWidth="3" strokeDasharray="100" strokeDashoffset={uploadProgress > 100 ? 25 : Math.max(0, 100 - uploadProgress)}></circle>
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center text-[8px] font-mono text-[#00F0FF]">{uploadProgress > 100 ? uploadProgress : `${uploadProgress}%`}</div>
                </div>
                <span className="text-[10px] font-mono text-[#00F0FF]/70 truncate max-w-[100px]">
                  {uploadMessage}
                </span>
                <button onClick={handleCancelUpload} className="p-1 rounded hover:bg-[#FF2A2A]/20 text-[#FF2A2A]/70 hover:text-[#FF2A2A] transition-colors ml-auto" title="Cancel upload">
                   <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
             <label className="cursor-pointer text-xs font-mono text-[#00F0FF] border border-[#00F0FF]/30 px-3 py-1 rounded hover:bg-[#00F0FF]/10 transition-colors inline-block">
               + UPLOAD FILE
               <input type="file" multiple className="hidden" onChange={handleUpload} />
             </label>
            )}
          </div>

        </div>
        
        <div className="p-4 border-t border-white/10 text-[10px] font-mono text-white/40 flex justify-between">
          <span>SYS_STATUS: <span className="text-[#00F0FF]">ONLINE</span></span>
        </div>
      </aside>

      {/* Main Canvas Area */}
      <main className="flex-1 relative flex flex-col">
        
        {/* Top bar controls */}
        <div className="absolute top-0 right-0 p-4 z-30 flex gap-4">
          <button 
            onClick={() => setIsDebateMode(!isDebateMode)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono border transition-all ${isDebateMode ? 'bg-[#FF2A2A]/10 border-[#FF2A2A] text-[#FF2A2A] shadow-[0_0_15px_rgba(255,42,42,0.2)]' : 'bg-white/5 border-white/10 text-white/50 hover:text-white/80'}`}
          >
            <Scale className="w-3.5 h-3.5" />
            DEBATE MODE: {isDebateMode ? 'ON' : 'OFF'}
          </button>
        </div>

        {/* The Neural Canvas */}
        <div className="absolute inset-0 z-0 overflow-hidden transition-all duration-700" 
             style={{
               backgroundImage: `radial-gradient(circle at 2px 2px, rgba(255,255,255,0.05) 1px, transparent 0)`,
               backgroundSize: `40px 40px`
             }}>
          
          {!isDebateMode ? (
            /* STANDARD MODE */
            <>
              <svg className="absolute inset-0 w-full h-full pointer-events-none">
                <path d="M 400 300 Q 550 150 700 200" fill="none" stroke="#00F0FF" strokeWidth="1.5" className="opacity-50 drop-shadow-[0_0_5px_#00F0FF]" strokeDasharray="4 4" />
                <path d="M 400 300 Q 500 450 650 400" fill="none" stroke="#B026FF" strokeWidth="1.5" className="opacity-50 drop-shadow-[0_0_5px_#B026FF]" strokeDasharray="4 4" />
              </svg>


              {/* Dynamic Query & Answer Node */}
              {lastQuery && (
                <div className="absolute top-[150px] left-[200px] w-[400px] glass-panel rounded-lg p-6 z-10 shadow-[0_0_40px_rgba(0,240,255,0.15)] border-[#00F0FF]/40">
                  <div className="text-[10px] font-mono text-[#00F0FF] mb-2 flex items-center gap-2">
                    <Activity className="w-3 h-3" /> QUERY_NODE
                  </div>
                  <p className="text-lg font-medium mb-4">{lastQuery}</p>
                  
                  {isSearching ? (
                    <div className="text-sm text-white/50 animate-pulse">Synthesizing...</div>
                  ) : (
                    <div className="text-sm text-white/90 leading-relaxed group-hover:pr-6">
                      {answer}
                    </div>
                  )}
                  {!isSearching && answer && (
                     <button onClick={copyAnswer} className="absolute top-4 right-4 p-1.5 rounded-md bg-white/5 hover:bg-[#00F0FF]/20 text-white/50 hover:text-[#00F0FF] transition-colors opacity-0 group-hover:opacity-100">
                        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                     </button>
                  )}
                </div>
              )}

              {/* Dynamic Source Nodes */}
              {sources.map((src: any, idx: number) => {
                // Layout vertically on the right side
                const top = 100 + (idx * 110);
                const left = 650 + (idx % 2 === 0 ? 0 : 40); // Slight zig-zag for organic feel
                
                return (
                  <div key={idx} style={{ top: `${top}px`, left: `${left}px` }} onClick={() => setActiveCitation(idx)} className="absolute w-72 glass-panel rounded-lg p-4 z-10 border-white/10 opacity-80 hover:opacity-100 transition-opacity cursor-pointer hover:border-[#00F0FF]/50 hover:shadow-[0_0_20px_rgba(0,240,255,0.2)]">
                    <div className="text-[10px] font-mono text-white/50 mb-2 flex justify-between">
                      <span className="truncate w-3/4">{src.source_document} [{src.marker}]</span>
                      <span className="text-[#00F0FF]">SIM: {src.rerank_score ? src.rerank_score.toFixed(2) : 'N/A'}</span>
                    </div>
                    <p className="text-xs text-[#B026FF] font-mono truncate">{src.section_heading}</p>
                  </div>
                );
              })}

            </>
          ) : (
            /* DEBATE MODE */
            <div className="w-full h-full flex pt-20 relative">
              {/* Conflict Line Divider */}
              <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-[#FF2A2A]/50 to-transparent shadow-[0_0_15px_#FF2A2A]"></div>
              
              {/* Agent 1: Strict Academic */}
              <div className="flex-1 p-12 flex flex-col items-end text-right">
                <div className="w-96 glass-panel rounded-lg p-5 border-white/10 shadow-lg">
                  <div className="text-[10px] font-mono text-white/50 mb-3 flex items-center justify-end gap-2">
                    <span className="text-[#00F0FF]">STRICT ACADEMIC</span>
                    <Activity className="w-3 h-3" /> 
                  </div>
                  <p className="text-sm leading-relaxed mb-4 text-white/90">
                    According to <span className="text-[#00F0FF] hover:underline cursor-pointer">handbook.md</span>, employees accrue 1.5 days per month. The document does not specify provisions for part-time workers, so I cannot assume they receive the same rate.
                  </p>
                </div>
              </div>

              {/* Agent 2: Creative Synthesizer */}
              <div className="flex-1 p-12 flex flex-col items-start">
                <div className="w-96 glass-panel rounded-lg p-5 border-[#FF2A2A]/30 shadow-[0_0_30px_rgba(255,42,42,0.1)] relative">
                  {/* Conflict indicator connecting the two */}
                  <div className="absolute top-1/2 -left-24 w-24 h-px bg-[#FF2A2A] opacity-50 shadow-[0_0_10px_#FF2A2A]"></div>
                  <div className="absolute top-1/2 -left-24 w-2 h-2 rounded-full bg-[#FF2A2A] shadow-[0_0_10px_#FF2A2A] -translate-y-1/2"></div>
                  
                  <div className="text-[10px] font-mono text-white/50 mb-3 flex items-center justify-start gap-2">
                    <Activity className="w-3 h-3" />
                    <span className="text-[#B026FF]">CREATIVE SYNTHESIZER</span>
                  </div>
                  <p className="text-sm leading-relaxed mb-4 text-white/90">
                    While the handbook states 1.5 days for full-time employees, standard industry practice outlined in <span className="text-[#B026FF] hover:underline cursor-pointer">onboarding.pdf</span> implies part-time employees likely receive a pro-rated amount based on hours worked.
                  </p>
                  
                  <div className="mt-4 p-2 bg-[#FF2A2A]/10 border border-[#FF2A2A]/20 rounded text-[10px] font-mono text-[#FF2A2A] flex items-start gap-2">
                    <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                    <span>CONFLICT: SYNTHESIZER EXTRAPOLATED BEYOND EXPLICIT TEXT. REVIEW REQUIRED.</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Input Area (Hidden in Debate mode for clarity, or kept minimal) */}
        <div className={`absolute bottom-8 left-1/2 -translate-x-1/2 w-full max-w-2xl z-20 transition-opacity duration-500 ${isDebateMode ? 'opacity-20 hover:opacity-100' : 'opacity-100'}`}>
          <div className="glass-panel rounded-full p-2 pl-6 flex items-center gap-4 shadow-[0_10px_40px_rgba(0,0,0,0.5)] focus-within:border-[#00F0FF]/50 focus-within:shadow-[0_0_20px_rgba(0,240,255,0.1)] transition-all">
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Stream query or hold space to speak..." 
              className="flex-1 bg-transparent border-none outline-none text-sm placeholder:text-white/30"
            />
            <button onClick={toggleRecording} className={`p-3 rounded-full transition-colors group ${isRecording ? 'bg-[#FF2A2A]/20 shadow-[0_0_15px_rgba(255,42,42,0.4)]' : 'bg-white/5 hover:bg-[#00F0FF]/10'}`}>
              <Mic className={`w-4 h-4 ${isRecording ? 'text-[#FF2A2A] animate-pulse' : 'text-white/50 group-hover:text-[#00F0FF]'}`} />
            </button>
            <button onClick={handleSearch} disabled={isSearching} className="p-3 bg-white/10 hover:bg-white/20 rounded-full transition-colors mr-1 disabled:opacity-50">
              <Search className="w-4 h-4 text-white" />
            </button>
          </div>
        </div>
      </main>

      {/* Holographic Citation Modal (Overlay) */}
      {activeCitation !== null && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#0A0A0A]/80 backdrop-blur-md transition-all">
          <div className="relative w-full max-w-3xl glass-panel rounded-xl p-8 border-[#00F0FF]/50 shadow-[0_0_60px_rgba(0,240,255,0.15)] animate-in fade-in zoom-in-95 duration-200">
            
            <button 
              onClick={() => setActiveCitation(null)}
              className="absolute top-6 right-6 text-white/50 hover:text-white bg-white/5 hover:bg-white/10 p-2 rounded-full transition-colors"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-4 mb-6">
              <div className="flex-1">
                <div className="text-[10px] font-mono text-[#00F0FF] mb-1">SOURCE DOCUMENT</div>
                <h2 className="text-xl font-medium text-white">{sources[activeCitation]?.source_document}</h2>
              </div>
              <div className="text-right">
                <div className="text-[10px] font-mono text-white/40 mb-1">SECTION</div>
                <div className="text-sm font-mono">{sources[activeCitation]?.section_heading}</div>
              </div>
            </div>

            <div className="relative p-6 bg-white/5 rounded-lg border border-white/10 font-sans text-sm leading-relaxed text-white/80 shadow-inner max-h-[300px] overflow-y-auto">
              <p>
                {sources[activeCitation]?.text || "Loading chunk context..."}
              </p>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#22C55E]/10 border border-[#22C55E]/30 text-[#22C55E] text-xs font-mono">
                <ShieldCheck className="w-3.5 h-3.5" />
                SCORE: {sources[activeCitation]?.rerank_score?.toFixed(2)}
              </div>
              <div className="text-[10px] font-mono text-white/40">
                CITATION VERIFIER / STRICT
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
