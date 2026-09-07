import re
with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

bad_block = """        <div className="flex justify-between items-center mb-6">
           <button onClick={() => setMobileMenuOpen(true)} className="md:hidden text-ink-secondary hover:text-ink" aria-label="Open menu">
             <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/></svg>
           </button>
           <div className="flex items-center gap-4">
             {conversationId && (
               <button onClick={handleExport} className="text-[11px] font-mono uppercase tracking-wider text-ink-secondary hover:text-ink border border-border px-3 py-1 bg-surface-card transition-colors">
                 Export .md
               </button>
             )}
             {conversationId && (
               <button onClick={() => setConversationId(null)} className="text-[11px] font-mono uppercase tracking-wider text-accent hover:bg-accent-tint border border-accent px-3 py-1 transition-colors" aria-label="Start new chat">
                 New Search
               </button>
             )}
           </div>
        </div>"""

if bad_block in text:
    text = text.replace(bad_block, "")
else:
    print("Could not find bad_block")

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)
