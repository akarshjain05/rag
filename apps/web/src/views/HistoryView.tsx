// @ts-nocheck
// @ts-nocheck

import { createPortal } from "react-dom";

import React, { useState, useEffect } from 'react';
import { fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from '../lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbsUp, ThumbsDown, LogOut, Moon, Sun, Menu, MoreHorizontal, Copy } from 'lucide-react';




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
 <div className="text-ink-secondary">Loading...</div>
 ) : conversations.length === 0 ? (
 <div className="text-ink-secondary">No history found.</div>
 ) : (
 <div className="flex flex-col gap-2">
 {(conversations || []).map(c => (
 <button 
 key={c.id} 
 onClick={() => onSelect(c.id)}
 className="flex justify-between items-center p-4 bg-surface-card border border-border rounded-sm hover:border-accent hover:text-accent transition-colors cursor-pointer text-left focus-visible:focus-visible:ring-2 focus-visible:ring-accent"
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



