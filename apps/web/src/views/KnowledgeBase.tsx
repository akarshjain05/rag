// @ts-nocheck
import React, { useState, useEffect, useRef } from 'react';
import { fetchDocuments, deleteDocument, ingest } from '../lib/api';
import { Folder, FileText, Trash2 } from 'lucide-react';
import Modal from '../components/ui/Modal';

export default function KnowledgeBase() {
 const [docs, setDocs] = useState<any[]>([]);
 const [loading, setLoading] = useState(true);
 const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
 const [uploading, setUploading] = useState(false);
 const [progress, setProgress] = useState<{pct: string | number, msg: string} | null>(null);
 const [modal, setModal] = useState<any>(null);
 const fileInputRef = useRef<HTMLInputElement>(null);

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
 if (fileInputRef.current) fileInputRef.current.value = '';
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
 <div className="flex-1 flex flex-col overflow-hidden bg-surface-card">
 <input 
  ref={fileInputRef} 
  type="file" 
  multiple 
  onChange={handleUpload} 
  className="hidden" 
  disabled={uploading} 
 />
 <div className="flex justify-end items-center p-6 border-b border-border">
 <div className="relative">
 {selectedDocs.size > 0 ? (
 <button onClick={handleBulkDelete} className="px-4 py-2 border border-accent text-accent hover:bg-accent-tint rounded-sm text-sm font-medium transition-colors flex items-center gap-2 cursor-pointer">
 <Trash2 className="w-4 h-4" /> Delete {selectedDocs.size} Selected
 </button>
 ) : (
 <button 
  onClick={() => fileInputRef.current?.click()} 
  className="px-4 py-2 border border-accent text-accent hover:bg-accent-tint hover:text-accent rounded-sm text-sm font-medium transition-colors disabled:opacity-50 cursor-pointer" 
  disabled={uploading}
 >
 {uploading ? "Uploading..." : "+ Upload File"}
 </button>
 )}
 </div>
 </div>
 
 {uploading && progress && (
 <div className="m-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-sm flex justify-between items-center text-sm text-blue-500">
 <span>{progress.msg}</span>
 <span className="font-mono">{progress.pct}</span>
 </div>
 )}

 <div className="flex-1 overflow-auto">
 {loading ? (
 <div className="p-8 text-center text-ink-secondary">Loading documents...</div>
 ) : docs.length === 0 ? (
 <div className="p-12 text-center text-ink-secondary flex flex-col items-center">
 <div 
   className="cursor-pointer w-20 h-20 rounded-full flex items-center justify-center transition-colors hover:bg-surface-card" 
   onClick={() => fileInputRef.current?.click()}
 >
   <Folder className="w-10 h-10 opacity-40 hover:opacity-80 transition-opacity" />
 </div>
 <p className="mt-2">Your knowledge base is empty.</p>
 <p className="text-sm mt-1 opacity-60">Upload PDFs, Markdown, or text files to begin.</p>
 </div>
 ) : (
 <table className="w-full text-sm text-left">
 <thead className="text-xs uppercase bg-surface-card border-b border-border">
 <tr>
 <th className="px-6 py-4 w-12 text-center">
 <input 
 type="checkbox" 
 className="rounded border-border cursor-pointer"
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
 className="rounded border-border cursor-pointer"
 checked={selectedDocs.has(doc)}
 onChange={() => toggleSelect(doc)}
 />
 </td>
 <td className="px-6 py-4 flex items-center gap-3">
 <FileText className="w-4 h-4 text-ink-muted" />
 {doc}
 </td>
 <td className="px-6 py-4 text-right">
 <button onClick={() => handleDelete(doc)} className="text-ink-muted hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all p-1 cursor-pointer">
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

