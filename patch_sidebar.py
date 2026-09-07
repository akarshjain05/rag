with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

sidebar_vars = """function Sidebar({ theme, setTheme, mobileMenuOpen, setMobileMenuOpen, currentView, setCurrentView, activeConversationId, setActiveConversationId, refreshTrigger, onLogout }) {
  const [conversations, setConversations] = React.useState([]);"""

sidebar_vars_new = """function Sidebar({ theme, setTheme, mobileMenuOpen, setMobileMenuOpen, currentView, setCurrentView, activeConversationId, setActiveConversationId, refreshTrigger, onLogout, onRefreshTrigger }) {
  const [conversations, setConversations] = React.useState([]);
  const [dropdownId, setDropdownId] = React.useState(null);

  const handleDelete = async (id) => {
    try {
      const { deleteConversation } = await import('./lib/api');
      await deleteConversation(id);
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setCurrentView('chat');
      }
      setDropdownId(null);
      if (onRefreshTrigger) onRefreshTrigger();
    } catch (e) {
      console.error(e);
    }
  };"""

text = text.replace(sidebar_vars, sidebar_vars_new)

history_map = """          {conversations.map(c => (
            <button
              key={c.id}
              onClick={() => { setActiveConversationId(c.id); setCurrentView('chat'); setMobileMenuOpen(false); }}
              className={`text-left font-sans text-[13px] py-1.5 truncate transition-colors ${currentView === 'chat' && activeConversationId === c.id ? 'text-ink border-l-2 border-accent pl-2 -ml-[1px]' : 'text-ink-secondary hover:text-ink pl-[11px]'}`}
            >
              {c.title}
            </button>
          ))}"""

history_map_new = """          {conversations.map(c => (
            <div key={c.id} className="group relative flex items-center pr-2">
              <button
                onClick={() => { setActiveConversationId(c.id); setCurrentView('chat'); setMobileMenuOpen(false); }}
                className={`flex-1 text-left font-sans text-[13px] py-1.5 truncate transition-colors ${currentView === 'chat' && activeConversationId === c.id ? 'text-ink border-l-2 border-accent pl-2 -ml-[1px]' : 'text-ink-secondary hover:text-ink pl-[11px]'}`}
              >
                {c.title}
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); setDropdownId(dropdownId === c.id ? null : c.id); }}
                className="opacity-0 group-hover:opacity-100 p-1 text-ink-muted hover:text-ink transition-opacity rounded-sm hover:bg-border"
              >
                <MoreHorizontal className="w-3 h-3" />
              </button>
              {dropdownId === c.id && (
                <div className="absolute right-0 top-full mt-1 w-32 bg-surface-card border border-border shadow-md z-50 py-1">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(c.id); }}
                    className="w-full text-left px-3 py-1.5 text-xs text-danger hover:bg-danger-tint flex items-center gap-2"
                  >
                    <Trash2 className="w-3 h-3" /> Delete
                  </button>
                </div>
              )}
            </div>
          ))}"""

text = text.replace(history_map, history_map_new)

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)

