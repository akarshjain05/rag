import React, { useState, useEffect } from 'react';
import { verifyAuth, fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from './lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbUp, ThumbDown, LogOut } from 'lucide-react';

export default function App() {
  const [apiKey, setApiKey] = useState<string | null>(import.meta.env.VITE_API_KEY || localStorage.getItem('apiKey'));
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentView, setCurrentView] = useState<'chat' | 'knowledge' | 'history' | 'insights' | 'settings'>('chat');
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

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
          {currentView === 'chat' && <ChatView conversationId={activeConversationId} setConversationId={setActiveConversationId} />}
          {currentView === 'knowledge' && <KnowledgeBase />}
          {currentView === 'history' && <HistoryView onSelect={(id) => { setActiveConversationId(id); setCurrentView('chat'); }} />}
          {(currentView === 'insights' || currentView === 'settings') && (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              Coming in v1.5
            </div>
          )}
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
        <h1 className="text-2xl font-semibold mb-2">Sign in to Omniscient</h1>
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

function Sidebar({ currentView, setCurrentView, onLogout }) {
  const navItems = [
    { id: 'chat', icon: MessageCircle, label: 'Ask' },
    { id: 'knowledge', icon: Folder, label: 'Knowledge base' },
    { id: 'history', icon: Clock, label: 'History' },
    { id: 'insights', icon: BarChart, label: 'Insights' },
  ];

  return (
    <div className="w-[220px] bg-gray-100 dark:bg-[#0A0A0A] border-r border-gray-200 dark:border-white/10 flex flex-col p-4">
      <div className="flex items-center gap-3 mb-8 px-2">
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white">OM</div>
        <span className="font-semibold tracking-wide">Omniscient</span>
      </div>
      
      <div className="flex flex-col gap-1">
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => setCurrentView(item.id)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${currentView === item.id ? 'bg-white dark:bg-white/10 text-black dark:text-white font-medium shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-white/5'}`}
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-auto flex flex-col gap-1">
        <button
          onClick={() => setCurrentView('settings')}
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${currentView === 'settings' ? 'bg-white dark:bg-white/10 text-black dark:text-white font-medium shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-white/5'}`}
        >
          <Settings className="w-4 h-4" />
          Settings
        </button>
        <button
          onClick={onLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-red-500 hover:bg-red-500/10"
        >
          <LogOut className="w-4 h-4" />
          Log out
        </button>
      </div>
    </div>
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
                className="flex justify-between items-center p-4 bg-white dark:bg-[#0A0A0A] border border-gray-200 dark:border-white/10 rounded-xl hover:border-blue-500 transition-colors text-left"
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

function ChatView({ conversationId, setConversationId }) {
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

  const isHighConfidence = confidenceInfo?.composite >= 0.7;
  const isLowConfidence = confidenceInfo?.composite < 0.4;

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Main Chat Thread */}
      <div className="flex-1 flex flex-col p-6 overflow-hidden relative">
        <div className="flex justify-between items-center mb-4">
          <div className="text-xs text-gray-500 font-mono">
            Conversation: {conversationId || "New"}
          </div>
          {conversationId && (
            <button onClick={() => setConversationId(null)} className="text-xs text-blue-500 hover:underline">
              Start new chat
            </button>
          )}
        </div>
        
        <div className="flex-1 overflow-auto flex flex-col gap-6 pb-20 pr-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`max-w-[85%] p-4 rounded-2xl text-sm leading-relaxed ${m.role === 'user' ? 'bg-gray-100 dark:bg-white/10' : ''}`}>
                {m.content}
              </div>
              
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
              className="flex-1 bg-transparent border-none outline-none px-3 text-sm"
            />
            <button 
              onClick={handleAsk} 
              disabled={loading || !query.trim()}
              className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Source Panel */}
      <div className="w-[300px] border-l border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-[#141414] p-6 flex flex-col overflow-hidden">
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
