// @ts-nocheck
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { fetchDocuments, deleteDocument, ingest } from '../lib/api';
import { Folder, FileText, Trash2, Upload, CloudUpload } from 'lucide-react';
import Modal from '../components/ui/Modal';

export default function KnowledgeBase() {
 const [docs, setDocs] = useState<any[]>([]);
 const [loading, setLoading] = useState(true);
 const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
 const [uploading, setUploading] = useState(false);
 const [progress, setProgress] = useState<{pct: string | number, msg: string} | null>(null);
 const [modal, setModal] = useState<any>(null);
 const [dragOver, setDragOver] = useState(false);
 const fileInputRef = useRef<HTMLInputElement>(null);

 const processFiles = useCallback(async (files: FileList | File[]) => {
 if (!files || files.length === 0) return;
 setUploading(true);
 setDragOver(false);
 setProgress({ pct: 0, msg: "Starting upload..." });
 try {
 const uploadRes = await ingest(files, (pct, msg) => {
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
 }, []);

 const handleUpload = (e) => {
 processFiles(e.target.files);
 };

 const handleDrop = useCallback((e: React.DragEvent) => {
 e.preventDefault();
 e.stopPropagation();
 setDragOver(false);
 if (e.dataTransfer.files?.length) {
   processFiles(e.dataTransfer.files);
 }
 }, [processFiles]);

 const handleDragOver = useCallback((e: React.DragEvent) => {
 e.preventDefault();
 e.stopPropagation();
 setDragOver(true);
 }, []);

 const handleDragLeave = useCallback((e: React.DragEvent) => {
 e.preventDefault();
 e.stopPropagation();
 setDragOver(false);
 }, []);

 useEffect(() => {
 fetchDocuments().then(res => {
 setDocs(res.source_documents || []);
 setLoading(false);
 }).catch(err => {
 console.error(err);
 setLoading(false);
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
 {/* Hidden file input — never visible, triggered via ref */}
 <input
   ref={fileInputRef}
   type="file"
   multiple
   onChange={handleUpload}
   className="hidden"
   disabled={uploading}
   accept=".pdf,.md,.txt,.html,.htm,.docx,.csv,.json"
 />

 <div className="flex justify-between items-center mb-6">
 <h2 className="text-xl font-semibold">Knowledge Base</h2>
 <div className="flex items-center gap-3">
 {selectedDocs.size > 0 ? (
 <button onClick={handleBulkDelete} className="px-4 py-2 border border-red-400 text-red-400 hover:bg-red-400/10 rounded-md text-sm font-medium transition-colors flex items-center gap-2">
 <Trash2 className="w-4 h-4" /> Delete {selectedDocs.size} Selected
 </button>
 ) : (
 <button
   onClick={() => fileInputRef.current?.click()}
   disabled={uploading}
   className="px-4 py-2 bg-accent text-white hover:bg-accent/90 rounded-md text-sm font-medium transition-all disabled:opacity-50 flex items-center gap-2 shadow-sm hover:shadow-md"
 >
 <Upload className="w-4 h-4" />
 {uploading ? "Uploading..." : "Upload Files"}
 </button>
 )}
 </div>
 </div>
 
 {uploading && progress && (
 <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-md flex justify-between items-center text-sm text-blue-400">
 <div className="flex items-center gap-3">
   <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
   <span>{progress.msg}</span>
 </div>
 <span className="font-mono text-xs bg-blue-500/20 px-2 py-1 rounded">{progress.pct}%</span>
 </div>
 )}

 <div
   className={`flex-1 overflow-auto bg-surface-card rounded-md border-2 transition-all duration-200 ${
     dragOver
       ? 'border-accent border-dashed bg-accent/5 scale-[1.005]'
       : 'border-border'
   }`}
   onDrop={handleDrop}
   onDragOver={handleDragOver}
   onDragLeave={handleDragLeave}
 >
 {loading ? (
 <div className="p-8 text-center text-ink-secondary">
   <div className="w-6 h-6 border-2 border-ink-muted border-t-transparent rounded-full animate-spin mx-auto mb-3" />
   Loading documents...
 </div>
 ) : docs.length === 0 ? (
 <div
   className="p-16 text-center text-ink-secondary flex flex-col items-center justify-center h-full cursor-pointer group"
   onClick={() => fileInputRef.current?.click()}
 >
 <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-5 transition-all duration-200 ${
   dragOver
     ? 'bg-accent/20 scale-110'
     : 'bg-surface-canvas group-hover:bg-accent/10'
 }`}>
   <CloudUpload className={`w-8 h-8 transition-colors ${dragOver ? 'text-accent' : 'text-ink-muted group-hover:text-accent'}`} />
 </div>
 <p className="text-base font-medium text-ink mb-1">
   {dragOver ? 'Drop files here' : 'Your knowledge base is empty'}
 </p>
 <p className="text-sm opacity-60 mb-4">
   {dragOver ? '' : 'Drag & drop files here, or click to browse'}
 </p>
 <p className="text-xs opacity-40">Supports PDF, Markdown, TXT, HTML, DOCX, CSV, JSON</p>
 </div>
 ) : (
 <table className="w-full text-sm text-left">
 <thead className="text-xs uppercase bg-surface-card border-b border-border sticky top-0">
 <tr>
 <th className="px-6 py-4 w-12 text-center">
 <input 
 type="checkbox" 
 className="rounded border-border accent-accent cursor-pointer"
 checked={docs.length > 0 && selectedDocs.size === docs.length}
 onChange={(e) => {
 if (e.target.checked) setSelectedDocs(new Set(docs));
 else setSelectedDocs(new Set());
 }}
 />
 </th>
 <th className="px-6 py-4 font-medium text-ink-secondary tracking-wider">Document Name</th>
 <th className="px-6 py-4 font-medium text-ink-secondary text-right tracking-wider">Actions</th>
 </tr>
 </thead>
 <tbody className="divide-y divide-border">
 {(docs || []).map((doc, i) => (
 <tr key={i} className="hover:bg-surface-canvas/50 transition-colors group">
 <td className="px-6 py-4 w-12 text-center">
 <input 
 type="checkbox" 
 className="rounded border-border accent-accent cursor-pointer"
 checked={selectedDocs.has(doc)}
 onChange={() => toggleSelect(doc)}
 />
 </td>
 <td className="px-6 py-4">
 <div className="flex items-center gap-3">
   <div className="w-8 h-8 rounded-md bg-accent/10 flex items-center justify-center flex-shrink-0">
     <FileText className="w-4 h-4 text-accent" />
   </div>
   <span className="font-medium truncate">{doc}</span>
 </div>
 </td>
 <td className="px-6 py-4 text-right">
 <button
   onClick={() => handleDelete(doc)}
   aria-label={`Delete ${doc}`}
   className="text-ink-muted hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all p-2 rounded-md"
 >
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
