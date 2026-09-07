with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

# 1. Add refreshTrigger to AppContent
text = text.replace(" const [activeConversationId, setActiveConversationId] = useState<string | null>(null);", " const [activeConversationId, setActiveConversationId] = useState<string | null>(null);\n const [refreshTrigger, setRefreshTrigger] = useState(0);")

# 2. Pass onNewMessage to ChatView in AppContent
text = text.replace("<ChatView conversationId={activeConversationId} setConversationId={setActiveConversationId} setMobileMenuOpen={setMobileMenuOpen} />", "<ChatView conversationId={activeConversationId} setConversationId={setActiveConversationId} setMobileMenuOpen={setMobileMenuOpen} onNewMessage={() => setRefreshTrigger(prev => prev + 1)} />")

# 3. Add onNewMessage to ChatView signature
text = text.replace("function ChatView({ conversationId, setConversationId, setMobileMenuOpen }) {", "function ChatView({ conversationId, setConversationId, setMobileMenuOpen, onNewMessage }) {")

# 4. Trigger onNewMessage when res.conversation_id is set
text = text.replace("setConversationId((prev) => prev || res.conversation_id);", "setConversationId((prev) => prev || res.conversation_id);\n      if (onNewMessage) onNewMessage();")

# 5. Fix Sidebar
import re
sidebar_pattern = re.compile(r"function Sidebar\(\{ currentView, setCurrentView, onLogout, theme, setTheme, mobileMenuOpen, setMobileMenuOpen \}\) \{(.*?)\s*</>\s*\);\s*\}", re.DOTALL)

new_sidebar = """function Sidebar({ currentView, setCurrentView, onLogout, theme, setTheme, mobileMenuOpen, setMobileMenuOpen, activeConversationId, setActiveConversationId, refreshTrigger }) {
  const [conversations, setConversations] = React.useState([]);

  React.useEffect(() => {
    import('./lib/api').then(({ fetchConversations }) => {
      fetchConversations().then(res => {
        setConversations(res.conversations || []);
      }).catch(err => console.error(err));
    });
  }, [refreshTrigger, currentView]);

  return (
    <>
      {/* Mobile Menu Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setMobileMenuOpen(false)} />
      )}
      
      <aside className={`fixed md:relative z-50 w-64 h-full bg-surface-sunken border-r border-border-strong flex flex-col transition-transform duration-300 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="p-6 pb-2 border-b border-border flex justify-between items-center">
          <h1 className="font-serif italic font-semibold text-[17px] text-ink tracking-wide cursor-pointer" onClick={() => { setActiveConversationId(null); setCurrentView('chat'); }}>Vellumiq</h1>
          <button className="md:hidden text-ink-secondary" onClick={() => setMobileMenuOpen(false)} aria-label="Close menu">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 border-b border-border">
            <button 
                onClick={() => { setActiveConversationId(null); setCurrentView('chat'); setMobileMenuOpen(false); }}
                className="w-full flex items-center justify-center gap-2 p-2 bg-surface border border-border hover:border-accent transition-colors text-[13px]"
            >
                <span className="font-mono uppercase tracking-wider text-[11px]">+ New Chat</span>
            </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-1">
          <div className="text-[10px] font-mono text-ink-muted uppercase tracking-widest mb-2 pl-2">Recent Chats</div>
          {conversations.map(c => (
            <button
              key={c.id}
              onClick={() => { setActiveConversationId(c.id); setCurrentView('chat'); setMobileMenuOpen(false); }}
              className={`text-left text-[13px] p-2 rounded-sm truncate ${currentView === 'chat' && activeConversationId === c.id ? 'bg-surface border border-border text-ink' : 'text-ink-secondary hover:text-ink hover:bg-surface-card'}`}
            >
              {c.title}
            </button>
          ))}
        </div>
        
        <div className="p-4 border-t border-border flex flex-col gap-2">
          <button
            onClick={() => { setCurrentView('knowledge'); setMobileMenuOpen(false); }}
            className={`text-left font-sans text-[13px] p-2 rounded-sm ${currentView === 'knowledge' ? 'bg-surface border border-border text-ink' : 'text-ink-secondary hover:text-ink'}`}
          >
            Knowledge Base
          </button>
          <button
            onClick={() => { setCurrentView('settings'); setMobileMenuOpen(false); }}
            className={`text-left font-sans text-[13px] p-2 rounded-sm ${currentView === 'settings' ? 'bg-surface border border-border text-ink' : 'text-ink-secondary hover:text-ink'}`}
          >
            Settings
          </button>
        </div>
        
        <div className="p-6 pt-4 border-t border-border flex justify-between items-center text-ink-muted">
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="p-1 hover:text-ink transition-colors" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button onClick={onLogout} className="p-1 hover:text-ink transition-colors text-[13px] text-accent font-sans hover:underline" aria-label="Log out">
              Log out
            </button>
        </div>
      </aside>
    </>
  );
}"""

text = sidebar_pattern.sub(new_sidebar, text)

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)
