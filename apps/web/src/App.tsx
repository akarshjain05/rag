import React, { useState, useEffect } from 'react';
import { verifyAuth, fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from './lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbsUp, ThumbsDown, LogOut, Moon, Sun, Menu } from 'lucide-react';

export default function App() {
  const [apiKey, setApiKey] = useState<string | null>(import.meta.env.VITE_API_KEY || localStorage.getItem('apiKey'));
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentView, setCurrentView] = useState<'chat' | 'knowledge' | 'history' | 'insights' | 'settings'>('chat');
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  
  const [theme, setTheme] = useState<'light' | 'dark'>(localStorage.getItem('theme') as 'light' | 'dark' || 'dark');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);
  useEffect(() => {
    if (apiKey) {
      verifyAuth().then(() => {
        setIsAuthenticated(true);
      }).catch(() => {
        setIsAuthenticated(false);
        localStorage.removeItem('apiKey');
        setApiKey(null);
      });
    } else {
      setIsAuthenticated(false);
    }
  }, [apiKey]);

  if (!isAuthenticated) {
    return <AuthScreen onAuth={(key) => { localStorage.setItem('apiKey', key); setApiKey(key); }} />;
  }

  return (
    <div className="min-h-screen bg-white dark:bg-[#0A0A0A] text-gray-900 dark:text-gray-100 font-sans flex items-center justify-center p-8">
      <div className="w-full max-w-7xl h-[85vh] bg-gray-50 dark:bg-[#141414] border border-gray-200 dark:border-white/10 rounded-2xl flex overflow-hidden shadow-2xl">
        <Sidebar 
          currentView={currentView} 
          setCurrentView={setCurrentView} 
          onLogout={() => { localStorage.removeItem('apiKey'); setApiKey(null); }} 
        />
        
        <main className="flex-1 flex overflow-hidden">
          {currentView === 'chat' && <ChatView conversationId={activeConversationId} setConversationId={setActiveConversationId} setMobileMenuOpen={setMobileMenuOpen} />}
          {currentView === 'knowledge' && <KnowledgeBase />}
          {currentView === 'history' && <HistoryView onSelect={(id) => { setActiveConversationId(id); setCurrentView('chat'); }} />}
          {(currentView === 'insights' || currentView === 'settings') && <InsightsView />}
        </main>
      </div>
    </div>
  );
}

function AuthScreen({ onAuth }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      localStorage.setItem('apiKey', key);
      await verifyAuth();
      onAuth(key);
    } catch (err) {
      setError("Invalid API Key");
      localStorage.removeItem('apiKey');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A] text-white">
      <div className="w-full max-w-md p-8 bg-[#141414] border border-white/10 rounded-xl shadow-2xl">
        <h1 className="text-2xl font-semibold mb-2">Sign in to Nexus</h1>
        <p className="text-gray-400 text-sm mb-6">Enter your API key to continue.</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input 
            type="password" 
            value={key} 
            onChange={e => setKey(e.target.value)}
            placeholder="sk-..." 
            className="p-3 rounded-lg bg-black/50 border border-white/10 focus:border-blue-500 focus:outline-none transition-colors"
          />
          {error && <div className="text-red-400 text-sm">{error}</div>}
          <button 
            type="submit" 
            disabled={loading || !key}
            className="p-3 bg-white text-black font-medium rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            {loading ? "Verifying..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Sidebar({ currentView, setCurrentView, onLogout, theme, setTheme, mobileMenuOpen, setMobileMenuOpen }) {
  const navItems = [
    { id: 'chat', icon: MessageCircle, label: 'Ask' },
    { id: 'knowledge', icon: Folder, label: 'Knowledge base' },
    { id: 'history', icon: Clock, label: 'History' },
    { id: 'insights', icon: BarChart, label: 'Insights' },
  ];

  return (
    <>
      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setMobileMenuOpen(false)} />
      )}
      
      <div className={`fixed md:relative z-50 w-64 h-full bg-[#FAFAFA] dark:bg-[#0A0A0A] border-r border-gray-200 dark:border-white/10 flex flex-col transition-transform duration-300 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="p-6 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold tracking-tighter">
              NX
            </div>
            <span className="font-semibold tracking-wide">Nexus</span>
          </div>
          <button className="md:hidden text-gray-500" onClick={() => setMobileMenuOpen(false)} aria-label="Close menu">
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 px-4 py-4 flex flex-col gap-2">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { setCurrentView(item.id as any); setMobileMenuOpen(false); }}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                currentView === item.id 
                  ? 'bg-gray-200 dark:bg-white/10 text-gray-900 dark:text-white font-medium' 
                  : 'text-gray-500 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500'
              }`}
              aria-label={item.label}
            >
              <item.icon className="w-4 h-4" />
              <span className="text-sm">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="p-4 flex flex-col gap-2">
          <button 
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-gray-500 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5 transition-all text-sm"
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
          </button>
          
          <button 
            onClick={() => { setCurrentView('settings'); setMobileMenuOpen(false); }}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-sm ${
              currentView === 'settings' 
                ? 'bg-gray-200 dark:bg-white/10 text-gray-900 dark:text-white font-medium' 
                : 'text-gray-500 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500'
            }`}
            aria-label="Settings"
          >
            <Settings className="w-4 h-4" />
            <span>Settings</span>
          </button>
          
          <button 
            onClick={onLogout}
            className="flex items-center gap-3 px-4 py-3 rounded-xl text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 transition-all mt-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            aria-label="Log out"
          >
            <LogOut className="w-4 h-4" />
            <span>Log out</span>
          </button>
        </div>
      </div>
    </>
  );
}

function KnowledgeBase() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<{pct: string | number, msg: string} | null>(null);

  useEffect(() => {
    fetchDocuments().then(res => {
      setDocs(res.source_documents || []);
      setLoading(false);
    }).catch(err => {
      console.error(err);
      setLoading(false);
    });
  }, []);

  const handleUpload = async (e) => {
    if (!e.target.files?.length) return;
    setUploading(true);
    setProgress({ pct: 0, msg: "Starting upload..." });
    try {
      await ingest(e.target.files, (pct, msg) => {
        setProgress({ pct, msg });
      }, null);
      const res = await fetchDocuments();
      setDocs(res.source_documents || []);
    } catch (err) {
      alert("Upload failed: " + err.message);
    } finally {
      setUploading(false);
      setProgress(null);
      e.target.value = null;
    }
  };

  const handleDelete = async (doc) => {
    if (confirm(`Delete ${doc}?`)) {
      await deleteDocument(doc);
      const res = await fetchDocuments();
      setDocs(res.source_documents || []);
    }
  };

  return (
    <div className="flex-1 p-8 flex flex-col overflow-hidden">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold">Knowledge Base</h2>
        <div className="relative">
          <input type="file" multiple onChange={handleUpload} className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" disabled={uploading} />
          <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50" disabled={uploading}>
            {uploading ? "Uploading..." : "+ Upload File"}
          </button>
        </div>
      </div>
      
      {uploading && progress && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg flex justify-between items-center text-sm text-blue-500">
          <span>{progress.msg}</span>
          <span className="font-mono">{progress.pct}</span>
        </div>
      )}

      <div className="flex-1 overflow-auto bg-white dark:bg-[#0A0A0A] rounded-xl border border-gray-200 dark:border-white/10">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading documents...</div>
        ) : docs.length === 0 ? (
          <div className="p-12 text-center text-gray-500 flex flex-col items-center">
            <Folder className="w-12 h-12 mb-4 opacity-20" />
            <p>Your knowledge base is empty.</p>
            <p className="text-sm mt-2 opacity-60">Upload PDFs, Markdown, or text files to begin.</p>
          </div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-gray-50 dark:bg-white/5 border-b border-gray-200 dark:border-white/10">
              <tr>
                <th className="px-6 py-4 font-medium text-gray-500">Document Name</th>
                <th className="px-6 py-4 font-medium text-gray-500 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc, i) => (
                <tr key={i} className="border-b border-gray-100 dark:border-white/5 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors group">
                  <td className="px-6 py-4 flex items-center gap-3">
                    <FileText className="w-4 h-4 text-gray-400" />
                    {doc}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button onClick={() => handleDelete(doc)} className="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all p-1">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function HistoryView({ onSelect }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    import('./lib/api').then(({ fetchConversations }) => {
      fetchConversations().then(res => {
        setConversations(res.conversations || []);
        setLoading(false);
      }).catch(() => setLoading(false));
    });
  }, []);

  return (
    <div className="flex-1 p-8 flex flex-col overflow-hidden">
      <h2 className="text-xl font-semibold mb-6">Conversation History</h2>
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="text-gray-500">Loading...</div>
        ) : conversations.length === 0 ? (
          <div className="text-gray-500">No history found.</div>
        ) : (
          <div className="flex flex-col gap-2">
            {conversations.map(c => (
              <button 
                key={c.id} 
                onClick={() => onSelect(c.id)}
                className="flex justify-between items-center p-4 bg-white dark:bg-[#0A0A0A] border border-gray-200 dark:border-white/10 rounded-xl hover:border-blue-500 transition-colors text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                <span className="font-medium">{c.title}</span>
                <span className="text-xs text-gray-400">{new Date(c.updated_at * 1000).toLocaleString()}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


function InsightsView() {
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    import('./lib/api').then(({ fetchInsights }) => {
      fetchInsights().then(res => setMetrics(res)).catch(err => console.error(err));
    });
  }, []);

  if (!metrics) return <div className="flex-1 flex items-center justify-center text-gray-500">Loading...</div>;

  const totalFeedback = metrics.thumbs_up + metrics.thumbs_down;
  const positiveRate = totalFeedback > 0 ? (metrics.thumbs_up / totalFeedback) * 100 : 0;

  return (
    <div className="flex-1 p-8 overflow-auto">
      <h2 className="text-2xl font-semibold mb-8">System Insights</h2>
      
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white dark:bg-[#0A0A0A] border border-gray-200 dark:border-white/10 rounded-2xl p-6">
          <div className="text-sm text-gray-500 mb-2">Total Queries Served</div>
          <div className="text-4xl font-light">{metrics.total_queries}</div>
        </div>
        
        <div className="bg-white dark:bg-[#0A0A0A] border border-gray-200 dark:border-white/10 rounded-2xl p-6">
          <div className="text-sm text-gray-500 mb-2">Avg Retrieval Confidence</div>
          <div className="text-4xl font-light">
            {(metrics.average_confidence * 100).toFixed(0)}<span className="text-xl text-gray-400">%</span>
          </div>
        </div>

        <div className="bg-white dark:bg-[#0A0A0A] border border-gray-200 dark:border-white/10 rounded-2xl p-6">
          <div className="text-sm text-gray-500 mb-2">Positive Feedback Rate</div>
          <div className="text-4xl font-light">
            {totalFeedback > 0 ? positiveRate.toFixed(0) : '--'}<span className="text-xl text-gray-400">%</span>
          </div>
          <div className="text-xs text-gray-400 mt-2">{totalFeedback} total ratings</div>
        </div>
      </div>

      <div className="bg-white dark:bg-[#0A0A0A] border border-gray-200 dark:border-white/10 rounded-2xl p-6">
        <h3 className="text-lg font-medium mb-6">User Satisfaction</h3>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-green-500 flex items-center gap-2"><ThumbsUp className="w-4 h-4" /> Helpful</span>
              <span>{metrics.thumbs_up}</span>
            </div>
            <div className="w-full bg-gray-100 dark:bg-white/5 rounded-full h-2">
              <div className="bg-green-500 h-2 rounded-full transition-all" style={{ width: `${totalFeedback > 0 ? (metrics.thumbs_up/totalFeedback)*100 : 0}%` }}></div>
            </div>
          </div>
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-red-500 flex items-center gap-2"><ThumbsDown className="w-4 h-4" /> Unhelpful</span>
              <span>{metrics.thumbs_down}</span>
            </div>
            <div className="w-full bg-gray-100 dark:bg-white/5 rounded-full h-2">
              <div className="bg-red-500 h-2 rounded-full transition-all" style={{ width: `${totalFeedback > 0 ? (metrics.thumbs_down/totalFeedback)*100 : 0}%` }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatView({ conversationId, setConversationId, setMobileMenuOpen }) {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState<number | null>(null);
  const [confidenceInfo, setConfidenceInfo] = useState<any>(null);

  const isInitialMount = React.useRef(true);
  const skipFetch = React.useRef(false);

  useEffect(() => {
    if (skipFetch.current) {
       skipFetch.current = false;
       return;
    }
    if (conversationId) {
      import('./lib/api').then(({ fetchConversation }) => {
        fetchConversation(conversationId).then(res => {
          if (res.history) {
            const mapped = [];
            res.history.forEach(t => {
              mapped.push({ role: 'user', content: t.user });
              mapped.push({ role: 'assistant', content: t.assistant });
            });
            setMessages(mapped);
          }
        }).catch(err => console.error(err));
      });
    } else {
      setMessages([]);
      setSources([]);
      setConfidenceInfo(null);
    }
  }, [conversationId]);

  const handleAsk = async () => {
    if (!query.trim()) return;
    const q = query;
    setQuery("");
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    
    try {
      const res = await ask({ question: q, conversationId, verifyCitations: true });
      if (!conversationId) {
          skipFetch.current = true;
          setConversationId(res.conversation_id);
      }
      
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer, markers: res.used_citation_markers }]);
      setSources(res.sources);
      setConfidenceInfo({
        composite: res.composite_confidence,
        retrieval: res.retrieval_confidence,
        completeness: res.completeness,
        coverage: res.citation_coverage
      });
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (index, isPositive) => {
    if (!conversationId) return;
    try {
      const { submitFeedback } = await import('./lib/api');
      await submitFeedback(conversationId, index / 2, isPositive);
      setMessages(prev => prev.map((msg, i) => i === index ? { ...msg, feedback: isPositive } : msg));
    } catch (err) {
      console.error("Failed to submit feedback", err);
    }
  };

  const isHighConfidence = confidenceInfo?.composite >= 0.7;
  const isLowConfidence = confidenceInfo?.composite < 0.4;

  return (
    <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
      {/* Main Chat Thread */}
      <div className="flex-1 flex flex-col p-6 overflow-hidden relative">
                <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileMenuOpen(true)} className="md:hidden text-gray-500 hover:text-gray-900 dark:hover:text-white" aria-label="Open menu">
              <Menu className="w-5 h-5" />
            </button>
            <div className="text-xs text-gray-500 font-mono">
              Conversation: {conversationId || "New"}
            </div>
          </div>
          {conversationId && (
            <button onClick={() => setConversationId(null)} className="text-xs text-blue-500 hover:underline" aria-label="Start new chat">
              Start new chat
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-auto flex flex-col gap-6 pb-20 pr-4" aria-live="polite">
          {messages.map((m, i) => (
            <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`max-w-[85%] p-4 rounded-2xl text-sm leading-relaxed ${m.role === 'user' ? 'bg-gray-100 dark:bg-white/10' : ''}`}>
                {m.content}
              </div>
              
              {m.role === 'assistant' && (
                <div className="flex items-center gap-4 mt-2 px-2 text-gray-400">
                  <button 
                    onClick={() => handleFeedback(i, true)}
                    className={`hover:text-green-500 transition-colors ${m.feedback === true ? 'text-green-500' : ''}`}
                    title="Helpful"
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                  </button>
                  <button 
                    onClick={() => handleFeedback(i, false)}
                    className={`hover:text-red-500 transition-colors ${m.feedback === false ? 'text-red-500' : ''}`}
                    title="Unhelpful"
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
              
              {m.role === 'assistant' && i === messages.length - 1 && confidenceInfo && (
                <details className="mt-2 text-xs">
                  <summary className="flex items-center gap-2 cursor-pointer list-none">
                    <span className={`px-3 py-1 rounded-full font-medium ${isHighConfidence ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400' : isLowConfidence ? 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400' : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-400'}`}>
                      {isHighConfidence ? 'High confidence' : isLowConfidence ? 'Low confidence' : 'Moderate confidence'}
                    </span>
                    <span className="text-gray-400">Show details</span>
                  </summary>
                  <div className="mt-2 p-3 bg-gray-50 dark:bg-white/5 rounded-lg flex gap-4 text-gray-500 font-mono">
                    <span>Retrieval: {confidenceInfo.retrieval?.toFixed(2) || 'N/A'}</span>
                    <span>Citations: {confidenceInfo.coverage?.toFixed(2) || 'N/A'}</span>
                    <span>Completeness: {confidenceInfo.completeness?.toFixed(2) || 'N/A'}</span>
                  </div>
                </details>
              )}
            </div>
          ))}
          {loading && (
             <div className="text-sm text-gray-400 flex items-center gap-2">
                <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
                Analyzing corpus...
             </div>
          )}
        </div>

        <div className="absolute bottom-6 left-6 right-6 pt-4 bg-gray-50/80 dark:bg-[#141414]/80 backdrop-blur-md">
          <div className="flex gap-2 items-center bg-white dark:bg-[#0A0A0A] border border-gray-200 dark:border-white/10 rounded-xl p-2 shadow-sm focus-within:border-blue-500 transition-colors">
            <input 
              type="text" 
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAsk()}
              placeholder="Ask a question..."
              className="flex-1 bg-transparent border-none outline-none px-3 text-sm focus-visible:ring-0"
            />
            <button 
              onClick={handleAsk}
              aria-label="Send message"  
              disabled={loading || !query.trim()}
              className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-[#0A0A0A]"
            >
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Source Panel */}
      <div className="w-full md:w-[300px] border-t md:border-t-0 md:border-l border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-[#141414] p-6 flex flex-col md:overflow-hidden min-h-[300px] md:min-h-0">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">Sources</h3>
        <div className="flex-1 overflow-auto flex flex-col gap-4">
          {sources.length === 0 ? (
            <div className="text-xs text-gray-400 text-center mt-10">No sources active</div>
          ) : (
            sources.map((s, i) => (
              <div key={i} className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl p-4 shadow-sm relative group cursor-pointer hover:border-blue-500 transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-gray-400" />
                  <span className="text-xs font-medium truncate flex-1">[{s.marker}] {s.source_document}</span>
                </div>
                <div className="text-[10px] text-gray-400 mb-2 truncate">{s.section_heading}</div>
                <p className="text-xs text-gray-600 dark:text-gray-300 font-serif leading-relaxed line-clamp-4">
                  {s.text}
                </p>
                <div className="mt-3 inline-block">
                  <span className="text-[9px] font-medium bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400 px-2 py-1 rounded-full">
                    Supported
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
