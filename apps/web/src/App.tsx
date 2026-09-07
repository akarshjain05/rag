import React, { useState, useEffect } from 'react';
import { verifyAuth, fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from './lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbsUp, ThumbsDown, LogOut, Moon, Sun, Menu } from 'lucide-react';


class ErrorBoundary extends React.Component<any, any> {
 constructor(props) {
 super(props);
 this.state = { hasError: false, error: null, info: null };
 }
 static getDerivedStateFromError(error) {
 return { hasError: true, error };
 }
 componentDidCatch(error, info) {
 this.setState({ info });
 console.error("ErrorBoundary caught an error", error, info);
 }
 render() {
 if (this.state.hasError) {
 return (
 <div style={{ padding: '20px', background: '#f8d7da', color: '#721c24' }}>
 <h2>Something went wrong.</h2>
 <details style={{ whiteSpace: 'pre-wrap' }}>
 {this.state.error && this.state.error.toString()}
 <br />
 {this.state.info && this.state.info.componentStack}
 </details>
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
 <div className="min-h-screen bg-surface-card text-ink font-sans flex items-center justify-center p-8">
 <div className="w-full max-w-7xl h-[85vh] bg-surface border border-border rounded-sm flex overflow-hidden ">
 <Sidebar 
          currentView={currentView} 
          setCurrentView={setCurrentView} 
          theme={theme}
          setTheme={setTheme}
          mobileMenuOpen={mobileMenuOpen}
          setMobileMenuOpen={setMobileMenuOpen}
          activeConversationId={activeConversationId}
          setActiveConversationId={setActiveConversationId}
          refreshTrigger={refreshTrigger}
          onLogout={() => { localStorage.removeItem('apiKey'); setApiKey(null); }} 
        />
 
 <div className="flex-1 flex overflow-hidden">
 {currentView === 'chat' && <ChatView conversationId={activeConversationId} setConversationId={setActiveConversationId} setMobileMenuOpen={setMobileMenuOpen} />}
 {currentView === 'knowledge' && <KnowledgeBase />}
 {currentView === 'history' && <HistoryView onSelect={(id) => { setActiveConversationId(id); setCurrentView('chat'); }} />}
 {currentView === 'insights' && <InsightsView />}
 {currentView === 'settings' && <SettingsView />}
 </div>
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
 <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A] text-ink">
 <div className="w-full max-w-md p-8 bg-[#141414] border border-white/10 rounded-sm ">
 <h1 className="text-2xl font-semibold mb-2">Sign in to Vellumiq</h1>
 <p className="text-ink-muted text-sm mb-6">Enter your API key to continue.</p>
 <form onSubmit={handleSubmit} className="flex flex-col gap-4">
 <input 
 type="password" 
 value={key} 
 onChange={e => setKey(e.target.value)}
 placeholder="sk-..." 
 className="p-3 rounded-sm bg-black/50 border border-white/10 focus:border-blue-500 focus:outline-none transition-colors"
 />
 {error && <div className="text-red-400 text-sm">{error}</div>}
 <button 
 type="submit" 
 disabled={loading || !key}
 className="p-3 bg-white text-black font-medium rounded-sm hover:border-l-2 border-accent transition-colors disabled:opacity-50"
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
    { id: 'knowledge', label: 'Knowledge Base' },
    { id: 'history', label: 'Search History' },
    { id: 'insights', label: 'Insights' },
  ];

  return (
    <>
      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setMobileMenuOpen(false)} />
      )}
      
      <aside className={`fixed md:relative z-50 w-64 h-full bg-surface-sunken border-r border-border-strong flex flex-col transition-transform duration-300 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="p-6 pb-2 border-b border-border flex justify-between items-center">
          <h1 className="font-serif italic font-semibold text-[17px] text-ink tracking-wide cursor-pointer" onClick={() => setCurrentView('chat')}>Vellumiq</h1>
          <button className="md:hidden text-ink-secondary" onClick={() => setMobileMenuOpen(false)} aria-label="Close menu">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <nav className="flex-1 p-6 flex flex-col gap-4 text-[13px]">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { setCurrentView(item.id as any); setMobileMenuOpen(false); }}
              className={`text-left font-sans ${currentView === item.id ? 'text-ink border-l-2 border-accent pl-3 -ml-[2px]' : 'text-ink-secondary pl-3 hover:text-ink'}`}
            >
              {item.label}
            </button>
          ))}
          <button
            onClick={() => { setCurrentView('settings'); setMobileMenuOpen(false); }}
            className={`text-left font-sans mt-auto ${currentView === 'settings' ? 'text-ink border-l-2 border-accent pl-3 -ml-[2px]' : 'text-ink-secondary pl-3 hover:text-ink'}`}
          >
            Settings
          </button>
        </nav>
        
        <div className="p-6 pt-4 border-t border-border">
          <button onClick={onLogout} className="text-[13px] text-accent font-sans hover:underline">
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}


function Modal({ isOpen, onClose, title, message, onConfirm, confirmText, isAlert }: any) {
 if (!isOpen) return null;
 return (
 <div className="fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4">
 <div className="bg-surface-sunken border border-border rounded-sm max-w-md w-full p-6 ">
 <h3 className="text-lg font-medium text-ink mb-2">{title}</h3>
 <p className="text-ink-secondary mb-6">{message}</p>
 <div className="flex justify-end gap-3">
 {!isAlert && (
 <button
 onClick={onClose}
 className="px-4 py-2 rounded-sm text-sm font-medium text-ink hover:bg-gray-100 transition-colors"
 >
 Cancel
 </button>
 )}
 <button
 onClick={() => { if (onConfirm) onConfirm(); onClose(); }}
 className={`px-4 py-2 rounded-sm text-sm font-medium text-ink transition-colors ${isAlert ? 'bg-transparent border border-accent text-accent hover:bg-accent-tint' : 'bg-transparent border border-accent text-accent hover:bg-accent-tint'}`}
 >
 {confirmText || 'Confirm'}
 </button>
 </div>
 </div>
 </div>
 );
}

function KnowledgeBase() {
 const [docs, setDocs] = useState<any[]>([]);
 const [loading, setLoading] = useState(true);
 const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
 const [uploading, setUploading] = useState(false);
 const [progress, setProgress] = useState<{pct: string | number, msg: string} | null>(null);
 const [modal, setModal] = useState<any>(null);

 const handleUpload = async (e) => {
 if (!e.target.files?.length) return;
 setUploading(true);
 setProgress({ pct: 0, msg: "Starting upload..." });
 try {
 const { ingest, fetchDocuments } = await import('./lib/api');
 await ingest(e.target.files, (pct, msg) => {
 setProgress({ pct, msg });
 }, null);
 const res = await fetchDocuments();
 setDocs(res.documents || res.source_documents || []);
 } catch (err) {
 setModal({ type: 'alert', title: 'Upload Failed', message: err.message, confirmText: 'OK' });
 } finally {
 setUploading(false);
 setProgress(null);
 e.target.value = null;
 }
 };


 useEffect(() => {
 import('./lib/api').then(({ fetchDocuments }) => {
 fetchDocuments().then(res => {
 setDocs(res.source_documents || []);
 setLoading(false);
 }).catch(err => {
 console.error(err);
 setLoading(false);
 });
 });
 }, []);

 const toggleSelect = (id: string) => {
 const next = new Set(selectedDocs);
 if (next.has(id)) next.delete(id);
 else next.add(id);
 setSelectedDocs(next);
 };

 const handleBulkDelete = () => {
 if (selectedDocs.size === 0) return;
 setModal({
 type: 'confirm',
 title: 'Bulk Delete',
 message: `Delete ${selectedDocs.size} documents?`,
 confirmText: 'Delete',
 onConfirm: async () => {
 const ids = Array.from(selectedDocs);
 setSelectedDocs(new Set());
 try {
 const { bulkDeleteDocuments } = await import('./lib/api');
 await bulkDeleteDocuments(ids);
 setDocs(prev => prev.filter(d => !ids.includes(d)));
 } catch (err) {
 console.error(err);
 }
 }
 });
 };
 const handleDelete = (doc) => {
 setModal({
 type: 'confirm',
 title: 'Delete Document',
 message: `Delete ${doc}?`,
 confirmText: 'Delete',
 onConfirm: async () => {
 await deleteDocument(doc);
 const res = await fetchDocuments();
 setDocs(res.source_documents || []);
 }
 });
 };

 return (
 <div className="flex-1 p-8 flex flex-col overflow-hidden">
 <div className="flex justify-between items-center mb-6">
 <h2 className="text-xl font-semibold">Knowledge Base</h2>
 <div className="relative">
 {selectedDocs.size > 0 ? (
 <button onClick={handleBulkDelete} className="px-4 py-2 border border-accent text-accent hover:bg-accent-tint rounded-sm text-sm font-medium transition-colors flex items-center gap-2 ">
 <Trash2 className="w-4 h-4" /> Delete {selectedDocs.size} Selected
 </button>
 ) : (
 <>
 <input type="file" multiple onChange={handleUpload} className="absolute inset-0 opacity-0 cursor-pointer w-full h-full" disabled={uploading} />
 <button className="px-4 py-2 border border-accent text-accent hover:bg-accent-tint rounded-sm text-sm font-medium transition-colors disabled:opacity-50" disabled={uploading}>
 {uploading ? "Uploading..." : "+ Upload File"}
 </button>
 </>
 )}
 </div>
 </div>
 
 {uploading && progress && (
 <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-sm flex justify-between items-center text-sm text-blue-500">
 <span>{progress.msg}</span>
 <span className="font-mono">{progress.pct}</span>
 </div>
 )}

 <div className="flex-1 overflow-auto bg-surface-card rounded-sm border border-border">
 {loading ? (
 <div className="p-8 text-center text-ink-secondary">Loading documents...</div>
 ) : docs.length === 0 ? (
 <div className="p-12 text-center text-ink-secondary flex flex-col items-center">
 <Folder className="w-12 h-12 mb-4 opacity-20" />
 <p>Your knowledge base is empty.</p>
 <p className="text-sm mt-2 opacity-60">Upload PDFs, Markdown, or text files to begin.</p>
 </div>
 ) : (
 <table className="w-full text-sm text-left">
 <thead className="text-xs uppercase bg-surface-card border-b border-border">
 <tr>
 <th className="px-6 py-4 w-12 text-center">
 <input 
 type="checkbox" 
 className="rounded border-border"
 checked={docs.length > 0 && selectedDocs.size === docs.length}
 onChange={(e) => {
 if (e.target.checked) setSelectedDocs(new Set(docs));
 else setSelectedDocs(new Set());
 }}
 />
 </th>
 <th className="px-6 py-4 font-medium text-ink-secondary">Document Name</th>
 <th className="px-6 py-4 font-medium text-ink-secondary text-right">Actions</th>
 </tr>
 </thead>
 <tbody>
 {docs.map((doc, i) => (
 <tr key={i} className="border-b border-gray-100 hover:bg-gray-50 transition-colors group">
 <td className="px-6 py-4 w-12 text-center">
 <input 
 type="checkbox" 
 className="rounded border-border"
 checked={selectedDocs.has(doc)}
 onChange={() => toggleSelect(doc)}
 />
 </td>
 <td className="px-6 py-4 flex items-center gap-3">
 <FileText className="w-4 h-4 text-ink-muted" />
 {doc}
 </td>
 <td className="px-6 py-4 text-right">
 <button onClick={() => handleDelete(doc)} className="text-ink-muted hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all p-1">
 <Trash2 className="w-4 h-4" />
 </button>
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 )}
 </div>
 <Modal isOpen={!!modal} onClose={() => setModal(null)} {...modal} isAlert={modal?.type === "alert"} />
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
 <div className="text-ink-secondary">Loading...</div>
 ) : conversations.length === 0 ? (
 <div className="text-ink-secondary">No history found.</div>
 ) : (
 <div className="flex flex-col gap-2">
 {conversations.map(c => (
 <button 
 key={c.id} 
 onClick={() => onSelect(c.id)}
 className="flex justify-between items-center p-4 bg-surface-card border border-border rounded-sm hover:border-blue-500 transition-colors text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
 >
 <span className="font-medium">{c.title}</span>
 <span className="text-xs text-ink-muted">{new Date(c.updated_at * 1000).toLocaleString()}</span>
 </button>
 ))}
 </div>
 )}
 </div>
 </div>
 );
}


function SettingsView() {
 const [keys, setKeys] = useState<any[]>([]);
 const [modal, setModal] = useState<any>(null);
 
 useEffect(() => {
 import('./lib/api').then(({ listApiKeys }) => {
 listApiKeys().then(res => setKeys(res)).catch(err => console.error(err));
 });
 }, []);

 const handleGenerate = async () => {
 try {
 const { generateApiKey } = await import('./lib/api');
 const res = await generateApiKey();
 if (res.api_key) {
 setKeys(prev => [res, ...prev]);
 }
 } catch (err) {
 console.error(err);
 }
 };

 const handleRevoke = (keyId: string) => {
 setModal({
 type: 'confirm',
 title: 'Revoke API Key',
 message: 'Revoke this key immediately?',
 confirmText: 'Revoke',
 onConfirm: async () => {
 try {
 const { revokeApiKey } = await import('./lib/api');
 await revokeApiKey(keyId);
 setKeys(prev => prev.filter(k => k.api_key !== keyId));
 } catch (err) {
 console.error(err);
 }
 }
 });
 };

 return (
 <div className="flex-1 p-8 overflow-auto">
 <h2 className="text-2xl font-semibold mb-8">Settings & API Keys</h2>
 
 <div className="max-w-2xl bg-surface-card border border-border rounded-sm p-6">
 <div className="flex justify-between items-center mb-6">
 <div>
 <h3 className="text-lg font-medium">API Keys</h3>
 <p className="text-sm text-ink-secondary">Manage API keys used for external access</p>
 </div>
 <button onClick={handleGenerate} className="border border-accent text-accent hover:bg-accent-tint px-4 py-2 rounded-sm text-sm font-medium transition-colors">
 Generate New Key
 </button>
 </div>
 
 <div className="space-y-4">
 {keys.length === 0 && <div className="py-4 font-serif italic text-ink-muted">No dynamic keys generated yet.</div>}
 {keys.map(k => (
 <div key={k.api_key} className="flex justify-between items-center p-4 border border-border rounded-sm bg-surface-card">
 <div>
 <div className="font-mono text-sm">{k.api_key}</div>
 <div className="text-xs text-ink-secondary mt-1">Created: {new Date(k.created_at * 1000).toLocaleString()}</div>
 </div>
 <button onClick={() => handleRevoke(k.api_key)} className="text-red-500 hover:text-red-600 text-sm font-medium">
 Revoke
 </button>
 </div>
 ))}
 </div>
 
 <div className="mt-6 p-4 bg-blue-50 text-blue-800 text-sm rounded-sm border border-blue-100 ">
 <strong>Note:</strong> Keys defined in the <code>API_KEYS</code> environment variable act as immutable root keys and are not shown here.
 </div>
 </div>
 <Modal isOpen={!!modal} onClose={() => setModal(null)} {...modal} isAlert={modal?.type === "alert"} />
 </div>
 );
}

function InsightsView() {
 const [metrics, setMetrics] = useState<any>(null);
 const [error, setError] = useState<string | null>(null);

 useEffect(() => {
 import('./lib/api').then(({ fetchInsights }) => {
 fetchInsights()
   .then(res => setMetrics(res))
   .catch(err => {
      console.error(err);
      setError("Failed to load insights. Please refresh the page.");
   });
 });
 }, []);

 if (error) return <div className="flex-1 flex items-center justify-center text-danger">{error}</div>;
 if (!metrics) return <div className="flex-1 flex items-center justify-center text-ink-secondary">Loading...</div>;

 const totalFeedback = metrics.thumbs_up + metrics.thumbs_down;
 const positiveRate = totalFeedback > 0 ? (metrics.thumbs_up / totalFeedback) * 100 : 0;

 return (
 <div className="flex-1 p-8 overflow-auto">
 <h2 className="text-2xl font-semibold mb-8">System Insights</h2>
 
 <div className="grid grid-cols-3 gap-6 mb-8">
 <div className="bg-surface-card border border-border rounded-sm p-6">
 <div className="text-sm text-ink-secondary mb-2">Total Queries Served</div>
 <div className="text-4xl font-light">{metrics.total_queries}</div>
 </div>
 
 <div className="bg-surface-card border border-border rounded-sm p-6">
 <div className="text-sm text-ink-secondary mb-2">Avg Retrieval Confidence</div>
 <div className="text-4xl font-light">
 {(metrics.average_confidence * 100).toFixed(0)}<span className="text-xl text-ink-muted">%</span>
 </div>
 </div>

 <div className="bg-surface-card border border-border rounded-sm p-6">
 <div className="text-sm text-ink-secondary mb-2">Positive Feedback Rate</div>
 <div className="text-4xl font-light">
 {totalFeedback > 0 ? positiveRate.toFixed(0) : '--'}<span className="text-xl text-ink-muted">%</span>
 </div>
 <div className="text-xs text-ink-muted mt-2">{totalFeedback} total ratings</div>
 </div>
 </div>

 <div className="bg-surface-card border border-border rounded-sm p-6">
 <h3 className="text-lg font-medium mb-6">User Satisfaction</h3>
 <div className="space-y-4">
 <div>
 <div className="flex justify-between text-sm mb-2">
 <span className="text-green-500 flex items-center gap-2"><ThumbsUp className="w-4 h-4" /> Helpful</span>
 <span>{metrics.thumbs_up}</span>
 </div>
 <div className="w-full bg-gray-100 rounded-full h-2">
 <div className="bg-green-500 h-2 rounded-full transition-all" style={{ width: `${totalFeedback > 0 ? (metrics.thumbs_up/totalFeedback)*100 : 0}%` }}></div>
 </div>
 </div>
 <div>
 <div className="flex justify-between text-sm mb-2">
 <span className="text-red-500 flex items-center gap-2"><ThumbsDown className="w-4 h-4" /> Unhelpful</span>
 <span>{metrics.thumbs_down}</span>
 </div>
 <div className="w-full bg-gray-100 rounded-full h-2">
 <div className="bg-red-500 h-2 rounded-full transition-all" style={{ width: `${totalFeedback > 0 ? (metrics.thumbs_down/totalFeedback)*100 : 0}%` }}></div>
 </div>
 </div>
 </div>
 </div>
 </div>
 );
}

function ChatView({ conversationId, setConversationId, setMobileMenuOpen }) {

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
          <span className="border-b border-dotted border-accent cursor-pointer">
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
  const [messages, setMessages] = React.useState([]);
  const [sources, setSources] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [activeCitation, setActiveCitation] = React.useState<number | null>(null);
  const [confidenceInfo, setConfidenceInfo] = React.useState<any>(null);

  const [compareDenseOnly, setCompareDenseOnly] = React.useState(false);
  const abortControllerRef = React.useRef<AbortController | null>(null);
  
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };
  const isInitialMount = React.useRef(true);
  const skipFetch = React.useRef(false);

  React.useEffect(() => {
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
            
            // Restore sources and confidence from the very last turn
            if (res.history.length > 0) {
              const lastTurn = res.history[res.history.length - 1];
              if (lastTurn.sources) {
                setSources(lastTurn.sources);
              }
              if (lastTurn.confidence_info) {
                setConfidenceInfo({
                  retrieval_confidence: lastTurn.confidence_info.retrieval,
                  citation_coverage: lastTurn.confidence_info.citation,
                  completeness: lastTurn.confidence_info.completeness,
                  composite_confidence: lastTurn.confidence_info.composite
                });
              }
            }
          }
        }).catch(console.error);
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
    setLoading(true);
    
    try {
      const { ask } = await import('./lib/api');
      const res = await ask({ question: q, conversationId, verifyCitations: true, compareDenseOnly });
      
      if (!conversationId && res.conversation_id) {
        skipFetch.current = true;
        setConversationId(res.conversation_id);
      }

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: res.answer, markers: res.used_citation_markers || [] }
      ]);
      setSources(res.sources || []);
      setConfidenceInfo({
        composite: res.composite_confidence,
        retrieval: res.retrieval_confidence,
        completeness: res.completeness,
        coverage: res.citation_coverage
      });
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Error: " + err.message }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (idx, isHelpful) => {
    if (!conversationId) return;
    const { submitFeedback } = await import('./lib/api');
    
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
    <div className="flex-1 bg-surface relative flex flex-col overflow-y-auto">
      
      {/* Top Header / Input Area */}
      <header className="px-6 md:px-12 pt-8 pb-6 max-w-4xl w-full mx-auto shrink-0">


        <div className="relative border-b border-border-strong pb-2 flex items-end">
          <input 
            type="text" 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAsk()}
            placeholder="Ask the archive..." 
            className="flex-1 bg-transparent border-none outline-none font-serif italic text-[18px] placeholder:text-ink-muted text-ink focus-visible:ring-0"
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
      </header>

      {/* Content Region: Answer & Citations */}
      <div className="flex-1 px-6 md:px-12 pt-0 pb-20 max-w-4xl w-full mx-auto flex flex-col gap-10">
        
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

        {messages.map((m, i) => (
           <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end mb-6' : 'items-start mb-10'}`}>
              
              {m.role === 'assistant' && i === messages.length - 1 && confidenceInfo && (
                <details className="mb-6 group/details">
                  <summary className="flex items-center gap-4 cursor-pointer list-none">
                    <div className={`inline-block px-2 py-0.5 border ${isHighConf ? 'border-success bg-success-tint text-success' : isLowConf ? 'border-danger bg-danger-tint text-danger' : 'border-warning bg-warning-tint text-warning'} font-mono text-[11px] uppercase tracking-widest -rotate-2`}>
                      {isHighConf ? 'Verified · High Confidence' : isLowConf ? 'Needs review · Low confidence' : 'Moderate confidence'}
                    </div>
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

              <div className={`${m.role === 'user' ? 'bg-surface-card border border-border px-4 py-3 rounded-none text-[14px] font-sans' : 'font-serif text-[16px] leading-[1.75] text-ink'} max-w-full whitespace-pre-wrap`}>
                 {m.role === 'assistant' ? renderContentWithCitations(m.content) : m.content}
              </div>

              {m.role === 'assistant' && (
                <div className="flex items-center gap-4 mt-3 text-ink-muted">
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

        {/* Sources Section */}
        {sources.length > 0 && (
           <div className="pt-8 border-t border-border">
             <h3 className="font-sans text-[13px] text-ink-secondary mb-4 uppercase tracking-wider">Sources</h3>
             
             <div className="flex flex-col gap-4">
               {sources.map((s, i) => (
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
                      <span className="inline-block px-2 py-0.5 border border-success bg-success-tint text-success font-mono text-[10px] uppercase tracking-wider">
                        Supported
                      </span>
                    </div>
                 </div>
               ))}
             </div>
           </div>
        )}
      </div>
    </div>
  );
}
