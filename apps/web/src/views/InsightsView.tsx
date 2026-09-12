// @ts-nocheck
// @ts-nocheck

import { createPortal } from "react-dom";

import React, { useState, useEffect } from 'react';
import { fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from '../lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbsUp, ThumbsDown, LogOut, Moon, Sun, Menu, MoreHorizontal, Copy } from 'lucide-react';




export default function InsightsView() {
 const [metrics, setMetrics] = useState<any>(null);
 const [error, setError] = useState<string | null>(null);

 useEffect(() => {
 import('../lib/api').then(({ fetchInsights }) => {
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

