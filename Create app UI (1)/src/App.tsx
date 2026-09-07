import React, { useState } from 'react';

export default function App() {
  const [query, setQuery] = useState('');
  const [isDebateMode, setIsDebateMode] = useState(false);
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

  // Mock data
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
    <div className="flex h-screen w-full bg-[var(--color-canvas)] text-[var(--color-ink)] overflow-hidden font-sans">
      
      {/* Left Sidebar: Navigation Rail */}
      <aside className="w-64 bg-[var(--color-surface-sunken)] border-r border-[var(--color-border-strong)] flex flex-col z-10 relative">
        <div className="p-6 pb-2 border-b border-[var(--color-border)]">
          <h1 className="font-serif italic font-semibold text-[17px] text-[var(--color-ink)] tracking-wide">Stacks</h1>
        </div>
        
        <nav className="flex-1 p-6 flex flex-col gap-4 text-[13px]">
          <button className="text-left font-sans text-[var(--color-ink)] border-l-2 border-[var(--color-accent)] pl-3 -ml-[2px]">
            Knowledge Base
          </button>
          <button className="text-left font-sans text-[var(--color-ink-secondary)] pl-3">
            Search History
          </button>
          <button className="text-left font-sans text-[var(--color-ink-secondary)] pl-3">
            Insights
          </button>
        </nav>
        
        <div className="p-6 pt-4 border-t border-[var(--color-border)]">
          <button className="text-[13px] text-[var(--color-accent)] font-sans">
            Log out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 bg-[var(--color-surface)] relative flex flex-col overflow-y-auto">
        
        {/* Top Header / Input Area */}
        <header className="p-12 pb-6 max-w-4xl w-full mx-auto">
          <div className="relative border-b border-[var(--color-border-strong)] pb-2 flex items-end">
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask the archive..." 
              className="flex-1 bg-transparent border-none outline-none font-serif italic text-[18px] placeholder:text-[var(--color-ink-muted)] text-[var(--color-ink)]"
            />
            <button className="ml-4 px-4 py-1 border border-[var(--color-accent)] text-[var(--color-accent)] font-sans text-[13px] hover:bg-[var(--color-accent-tint)] transition-colors">
              Ask
            </button>
          </div>
        </header>

        {/* Content Region: Answer & Citations */}
        <div className="flex-1 p-12 pt-6 max-w-4xl w-full mx-auto flex flex-col gap-10">
          
          {/* Mock Generated Answer */}
          <div className="prose max-w-none">
            <div className="flex items-center gap-4 mb-4">
               {/* Confidence Stamp */}
               <div className="inline-block px-2 py-0.5 border border-[var(--color-success)] bg-[var(--color-success-tint)] text-[var(--color-success)] font-mono text-[11px] uppercase tracking-widest -rotate-2">
                 Verified · High Confidence
               </div>
               <div className="font-mono text-[11px] text-[var(--color-ink-muted)]">
                 COMPOSITE SCORE: 0.91
               </div>
            </div>

            <p className="font-serif text-[16px] leading-[1.75] text-[var(--color-ink)]">
              Employees accrue vacation at a rate of 1.5 days per month<span 
                className="border-b border-dotted border-[var(--color-accent)] cursor-pointer"
                onClick={() => setActiveCitation(1)}
              >
              <sup className="font-mono text-[var(--color-accent)] ml-0.5">[1]</sup>
              </span>, starting from their first full month of employment. Time off must be requested at least two weeks in advance.
            </p>
          </div>

          {/* Source Document Cards */}
          <div className="pt-8 border-t border-[var(--color-border)]">
             <h3 className="font-sans text-[13px] text-[var(--color-ink-secondary)] mb-4">SOURCES</h3>
             
             <div className="flex flex-col gap-4">
                {/* Source Card 1 */}
                <div className="bg-[var(--color-surface-card)] border border-[var(--color-border)] border-t-[3px] border-t-[var(--color-accent)] p-4 flex flex-col gap-3">
                  <div className="flex items-baseline justify-between">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[12px] text-[var(--color-ink)]">handbook.md</span>
                      <span className="font-serif italic text-[13px] text-[var(--color-ink-muted)]">Vacation Policy</span>
                    </div>
                    <span className="font-mono text-[11px] text-[var(--color-ink-muted)]">CHUNK ID: hb::str::42</span>
                  </div>
                  <div className="font-serif text-[15px] leading-relaxed text-[var(--color-ink-secondary)] border-l-2 border-[var(--color-border-strong)] pl-4 italic">
                    "Employees accrue vacation at a rate of 1.5 days per month, starting from their first full month of employment."
                  </div>
                  <div className="flex justify-start mt-1">
                    <span className="inline-block px-2 py-0.5 border border-[var(--color-success)] bg-[var(--color-success-tint)] text-[var(--color-success)] font-mono text-[10px] uppercase tracking-wider">
                      Supported
                    </span>
                  </div>
                </div>

                {/* Source Card 2 */}
                <div className="bg-[var(--color-surface-card)] border border-[var(--color-border)] border-t-[3px] border-t-[var(--color-accent)] p-4 flex flex-col gap-3">
                  <div className="flex items-baseline justify-between">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[12px] text-[var(--color-ink)]">onboarding.pdf</span>
                      <span className="font-serif italic text-[13px] text-[var(--color-ink-muted)]">Time Off</span>
                    </div>
                    <span className="font-mono text-[11px] text-[var(--color-ink-muted)]">CHUNK ID: onb::fix::12</span>
                  </div>
                  <div className="font-serif text-[15px] leading-relaxed text-[var(--color-ink-secondary)] border-l-2 border-[var(--color-border-strong)] pl-4 italic">
                    "New hires should note their PTO accrues over time. No vacation time is advanced prior to the accrual period."
                  </div>
                </div>
             </div>
          </div>
          
        </div>
      </main>

    </div>
  );
}
