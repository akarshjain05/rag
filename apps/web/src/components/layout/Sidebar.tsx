// @ts-nocheck
import React, { useState, useEffect } from 'react';
import { createPortal } from "react-dom";
import { MessageCircle, Folder, Clock, BarChart, FileText, X, Trash2, Moon, Sun, MoreVertical } from 'lucide-react';

export default function Sidebar({ currentView, setCurrentView, theme, setTheme, mobileMenuOpen, setMobileMenuOpen, activeConversationId, setActiveConversationId, refreshTrigger, onRefreshTrigger }) {
  const [conversations, setConversations] = React.useState<any[]>([]);
  const [dropdownId, setDropdownId] = React.useState(null);

  const handleDelete = async (id) => {
    try {
      const { deleteConversation } = await import('../../lib/api');
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
  };

  React.useEffect(() => {
    import('../../lib/api').then(({ fetchConversations }) => {
      fetchConversations().then(res => {
        setConversations(res.conversations || []);
      }).catch(err => console.error(err));
    });
  }, [refreshTrigger, currentView]);

  return (
    <>
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setMobileMenuOpen(false)} />
      )}
      
      <aside className={`fixed md:relative z-50 w-64 h-full bg-surface-sunken border-r border-border-strong flex flex-col transition-transform duration-300 ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="p-6 pb-4 border-b border-border flex items-center justify-between">
          <h1 className="font-serif italic font-semibold text-[17px] text-ink tracking-wide cursor-pointer" onClick={() => { setActiveConversationId(null); setCurrentView('chat'); }}>Vellumiq</h1>
          <button 
            className="md:hidden text-ink-secondary hover:text-ink cursor-pointer hover:bg-surface-card p-1 rounded-md transition-colors"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-4 border-b border-border">
          <button 
            onClick={() => { setActiveConversationId(null); setCurrentView('chat'); setMobileMenuOpen(false); }}
            className="w-full text-center px-4 py-1.5 border border-border-strong hover:border-accent hover:text-accent hover:bg-surface-card rounded-md bg-transparent text-[13px] font-sans text-ink transition-colors cursor-pointer"
          >
            + New Research
          </button>
        </div>
        
        <nav className="flex-1 overflow-y-auto p-4 flex flex-col gap-1 min-h-0">
          <div className="px-2 py-2 mb-1 text-[10px] font-mono text-ink-muted uppercase tracking-widest">
            History
          </div>
          {(conversations || []).map(c => (
            <div key={c.id} className={`group relative flex items-center rounded-md cursor-pointer transition-colors ${(currentView === 'chat' && activeConversationId === c.id) || dropdownId === c.id ? 'bg-canvas text-ink' : 'text-ink-secondary hover:text-ink hover:bg-canvas'}`}>
              <button
                onClick={() => { setActiveConversationId(c.id); setMobileMenuOpen(false); }}
                className={`flex-1 text-left font-sans text-[13px] py-2.5 px-3 truncate rounded-md transition-colors cursor-pointer ${currentView === 'chat' && activeConversationId === c.id ? 'border-l-2 border-accent' : 'border-l-2 border-transparent'}`}
              >
                {c.title}
              </button>
              <div className={`absolute right-0 top-0 bottom-0 flex items-center pr-1 pl-6 transition-opacity rounded-r-md bg-gradient-to-l from-canvas from-60% to-transparent pointer-events-none ${dropdownId === c.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}>
                <button
                  id={`dropdown-btn-${c.id}`}
                  onClick={(e) => { e.stopPropagation(); setDropdownId(dropdownId === c.id ? null : c.id); }}
                  className="p-1 text-ink-muted hover:text-ink hover:bg-border/50 rounded-md transition-colors cursor-pointer pointer-events-auto"
                  aria-label="More options"
                >
                  <MoreVertical className="w-3.5 h-3.5" />
                </button>
              </div>
              {dropdownId === c.id && createPortal(
                <>
                  <div className="fixed inset-0 z-[100]" onClick={(e) => { e.stopPropagation(); setDropdownId(null); }} />
                  <div 
                    className="fixed z-[101] w-32 bg-surface-card border border-border shadow-md py-1 rounded-md"
                    style={{ 
                      top: document.getElementById(`dropdown-btn-${c.id}`)?.getBoundingClientRect().bottom + 4 || 0, 
                      left: document.getElementById(`dropdown-btn-${c.id}`)?.getBoundingClientRect().left || 0 
                    }}
                  >
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(c.id); }}
                      className="w-full text-left px-3 py-1.5 text-xs text-danger hover:bg-danger-tint flex items-center gap-2 cursor-pointer"
                    >
                      <Trash2 className="w-3 h-3" /> Delete
                    </button>
                  </div>
                </>,
                document.body
              )}
            </div>
          ))}
        </nav>
        
        <div className="p-4 border-t border-border flex flex-col gap-3">
          <button
            onClick={() => { setCurrentView('knowledge'); setMobileMenuOpen(false); }}
            className={`text-left text-[13px] font-sans px-3 py-2.5 rounded-md cursor-pointer transition-colors ${currentView === 'knowledge' ? 'text-ink bg-canvas' : 'text-ink-secondary hover:text-ink hover:bg-canvas'}`}
          >
            Knowledge Base
          </button>
        </div>

        <div className="p-6 pt-4 border-t border-border flex justify-between items-center text-ink-muted">
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="p-1.5 hover:text-ink hover:bg-canvas rounded-md transition-colors cursor-pointer" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
        </div>
      </aside>
    </>
  );
}
