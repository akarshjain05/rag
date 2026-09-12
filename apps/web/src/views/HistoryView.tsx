// @ts-nocheck
import React, { useState, useEffect } from 'react';
import { Clock, ArrowRight, MessageCircle } from 'lucide-react';

export default function HistoryView({ onSelect }) {
 const [conversations, setConversations] = useState<any[]>([]);
 const [loading, setLoading] = useState(true);

 useEffect(() => {
 import('../lib/api').then(({ fetchConversations }) => {
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
 <div className="text-ink-secondary text-center py-12">
   <div className="w-6 h-6 border-2 border-ink-muted border-t-transparent rounded-full animate-spin mx-auto mb-3" />
   Loading...
 </div>
 ) : conversations.length === 0 ? (
 <div className="text-ink-secondary text-center py-16 flex flex-col items-center">
   <div className="w-16 h-16 rounded-full bg-surface-card flex items-center justify-center mb-4">
     <Clock className="w-8 h-8 text-ink-muted" />
   </div>
   <p className="font-medium text-ink mb-1">No conversations yet</p>
   <p className="text-sm opacity-60">Start a new research session to see it here.</p>
 </div>
 ) : (
 <div className="flex flex-col gap-2">
 {(conversations || []).map(c => (
 <button 
 key={c.id} 
 onClick={() => onSelect(c.id)}
 className="flex justify-between items-center p-4 bg-surface-card border border-border rounded-md hover:border-accent hover:bg-accent-tint/30 hover:shadow-sm transition-all duration-200 text-left group focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
 >
 <div className="flex items-center gap-3 min-w-0">
   <div className="w-8 h-8 rounded-md bg-accent/10 flex items-center justify-center flex-shrink-0 group-hover:bg-accent/20 transition-colors">
     <MessageCircle className="w-4 h-4 text-accent" />
   </div>
   <span className="font-medium truncate">{c.title}</span>
 </div>
 <div className="flex items-center gap-2 flex-shrink-0 ml-4">
   <span className="text-xs text-ink-muted">{new Date(c.updated_at * 1000).toLocaleString()}</span>
   <ArrowRight className="w-4 h-4 text-ink-muted opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
 </div>
 </button>
 ))}
 </div>
 )}
 </div>
 </div>
 );
}
