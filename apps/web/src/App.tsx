// @ts-nocheck
import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar';
import ErrorBoundary from './components/ui/ErrorBoundary';
import ChatView from './views/ChatView';
import KnowledgeBase from './views/KnowledgeBase';
import HistoryView from './views/HistoryView';
import InsightsView from './views/InsightsView';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ErrorBoundary>
  );
}

function AppContent() {
  const [theme, setTheme] = useState<'light' | 'dark'>(localStorage.getItem('theme') as 'light' | 'dark' || 'dark');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const location = useLocation();
  const navigate = useNavigate();

  const currentView = location.pathname.startsWith('/chat') ? 'chat'
                    : location.pathname === '/knowledge' ? 'knowledge'
                    : location.pathname === '/history' ? 'history'
                    : location.pathname === '/insights' ? 'insights'
                    : 'chat';

  const match = location.pathname.match(/^\/chat\/(.+)$/);
  const activeConversationId = match ? match[1] : null;

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const setCurrentView = (view: string) => {
    if (view === 'chat') navigate('/chat');
    else if (view === 'knowledge') navigate('/knowledge');
    else if (view === 'history') navigate('/history');
    else if (view === 'insights') navigate('/insights');
  };

  const setActiveConversationId = (id: string | null) => {
    if (id) navigate(`/chat/${id}`);
    else navigate('/chat');
  };

  return (
    <div className="flex h-screen bg-surface-canvas text-ink font-sans">
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
        onRefreshTrigger={() => setRefreshTrigger(prev => prev + 1)}
      />
      <main className="flex-1 flex flex-col relative w-full h-full overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatView 
            conversationId={null} 
            setConversationId={setActiveConversationId}
            setMobileMenuOpen={setMobileMenuOpen}
            onNewMessage={() => setRefreshTrigger(prev => prev + 1)} 
          />} />
          <Route path="/chat/:id" element={<ChatView 
            conversationId={activeConversationId} 
            setConversationId={setActiveConversationId}
            setMobileMenuOpen={setMobileMenuOpen}
            onNewMessage={() => setRefreshTrigger(prev => prev + 1)} 
          />} />
          <Route path="/knowledge" element={<KnowledgeBase />} />
          <Route path="/history" element={<HistoryView onSelect={setActiveConversationId} />} />
          <Route path="/insights" element={<InsightsView />} />
        </Routes>
      </main>
    </div>
  );
}
