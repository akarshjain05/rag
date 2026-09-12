// @ts-nocheck
// @ts-nocheck

import { createPortal } from "react-dom";

import React, { useState, useEffect } from 'react';
import { fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from '../lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbsUp, ThumbsDown, LogOut, Moon, Sun, Menu, MoreHorizontal, Copy } from 'lucide-react';




import Modal from '../components/ui/Modal';
export default function KnowledgeBase() {
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
 const { ingest, fetchDocuments } = await import('../lib/api');
 const uploadRes = await ingest(e.target.files, (pct, msg) => {
 setProgress({ pct, msg });
 }, null);
 
 if (uploadRes && uploadRes.reports) {
    const failed = uploadRes.reports.find(r => r.error);
    if (failed) throw new Error(failed.error);
 }
 
 const res = await fetchDocuments();
 setDocs(res.documents || res.source_documents || []);
 } catch (err: any) {
 setModal({ type: 'alert', title: 'Upload Failed', message: err.message, confirmText: 'OK' });
 } finally {
 setUploading(false);
 setProgress(null);
 e.target.value = null;
 }
 };


 useEffect(() => {
 import('../lib/api').then(({ fetchDocuments }) => {
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
 const { bulkDeleteDocuments } = await import('../lib/api');
 await bulkDeleteDocuments(ids);
 setDocs(prev => prev.filter(d => !ids.includes(d)));
 } catch (err: any) {
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
 {(docs || []).map((doc, i) => (
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

