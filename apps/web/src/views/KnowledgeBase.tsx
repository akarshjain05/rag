// @ts-nocheck
import React, { useState, useEffect, useRef } from 'react';
import { fetchDocuments, deleteDocument, ingest } from '../lib/api';
import { Folder, FileText, Trash2, CloudUpload } from 'lucide-react';
import Modal from '../components/ui/Modal';

export default function KnowledgeBase() {
 const [docs, setDocs] = useState<any[]>([]);
 const [loading, setLoading] = useState(true);
 const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
 const [uploading, setUploading] = useState(false);
 const [uploadingFiles, setUploadingFiles] = useState<File[]>([]);
 const [dragOver, setDragOver] = useState(false);
 const [progress, setProgress] = useState<{pct: number, msg: string} | null>(null);
 const [modal, setModal] = useState<any>(null);
 const fileInputRef = useRef<HTMLInputElement>(null);

 const handleUpload = async (e) => {
 if (!e.target.files?.length) return;
 setUploading(true);
 setUploadingFiles(Array.from(e.target.files));
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
 setUploadingFiles([]);
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
 <div className="flex-1 flex flex-col overflow-hidden bg-surface-card relative">
 <input 
  ref={fileInputRef} 
  type="file" 
  multiple 
  onChange={handleUpload} 
  className="hidden" 
  disabled={uploading} 
 />
 <div className="absolute top-0 right-0 p-6 z-10">
 <div className="relative">
 {selectedDocs.size > 0 ? (
 <button onClick={handleBulkDelete} className="px-4 py-2 border border-accent text-accent hover:bg-accent-tint rounded-sm text-sm font-medium transition-colors flex items-center gap-2 cursor-pointer bg-surface-card">
 <Trash2 className="w-4 h-4" /> Delete {selectedDocs.size} Selected
 </button>
 ) : (
 <button 
  onClick={() => fileInputRef.current?.click()} 
  className="px-4 py-2 border border-accent text-accent hover:bg-accent-tint hover:text-accent rounded-sm text-sm font-medium transition-colors disabled:opacity-50 cursor-pointer bg-surface-card shadow-sm" 
  disabled={uploading}
 >
 {uploading ? "Uploading..." : "+ Upload File"}
 </button>
 )}
 </div>
 </div>
 
 <div className="flex-1 overflow-auto flex flex-col">
 {loading ? (
 <div className="flex-1 flex items-center justify-center text-ink-secondary">Loading documents...</div>
 ) : docs.length === 0 && uploadingFiles.length === 0 ? (
 <div 
   className="flex-1 flex flex-col items-center justify-center text-center text-ink-secondary p-12"
   onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
   onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
   onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload({ target: { files: e.dataTransfer.files }}); }}
 >
   <div 
     className={`cursor-pointer w-16 h-16 rounded-full flex items-center justify-center mb-5 transition-all duration-200 ${
       dragOver ? 'bg-accent/20 scale-110' : 'bg-surface-sunken hover:bg-accent/10 hover:scale-105'
     }`}
     onClick={() => fileInputRef.current?.click()}
   >
     <CloudUpload className={`w-8 h-8 transition-colors ${dragOver ? 'text-accent' : 'text-ink-muted'}`} />
   </div>
   <p className="font-medium text-ink mb-1">
     {dragOver ? 'Drop files here' : 'Your knowledge base is empty'}
   </p>
   <p className="text-sm opacity-60">
     {dragOver ? '' : 'Drag & drop files here, or click to browse'}
   </p>
 </div>
 ) : (
 <div className="pt-20 px-6 pb-6">
 <table className="w-full text-sm text-left">
 <thead className="text-xs uppercase bg-surface-card border-b border-border">
 <tr>
 <th className="px-4 py-4 w-12 text-center">
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
 <th className="px-4 py-4 font-medium text-ink-secondary">Document Name</th>
 <th className="px-4 py-4 font-medium text-ink-secondary text-right">Actions</th>
 </tr>
 </thead>
 <tbody>
 {uploadingFiles.map((file, i) => (
 <tr key={`uploading-${i}`} className="border-b border-border/50 bg-surface-sunken opacity-80">
 <td className="px-4 py-4 w-12 text-center">
 <div className="w-[13px] h-[13px] rounded border border-border/50 mx-auto"></div>
 </td>
 <td className="px-4 py-4 flex items-center gap-3 text-ink-muted">
 <FileText className="w-4 h-4" />
 {file.name}
 </td>
 <td className="px-4 py-4">
 <div className="flex items-center justify-end gap-2 text-xs text-ink-muted">
 {progress && (
 <>
 <svg className="transform -rotate-90 w-4 h-4">
 <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" fill="transparent" className="opacity-20" />
 <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" fill="transparent" className="text-accent transition-all duration-300" strokeDasharray="37.7" strokeDashoffset={37.7 - ((typeof progress.pct === 'number' ? progress.pct : parseInt(progress.pct.toString()) || 0) / 100 * 37.7)} />
 </svg>
 <span className="w-8 text-right tabular-nums">{String(progress.pct).replace('%', '')}%</span>
 </>
 )}
 </div>
 </td>
 </tr>
 ))}
 {(docs || []).map((doc, i) => (
 <tr key={i} className="border-b border-border/50 hover:bg-surface-sunken transition-colors group">
 <td className="px-4 py-4 w-12 text-center">
 <input 
 type="checkbox" 
 className="rounded border-border cursor-pointer"
 checked={selectedDocs.has(doc)}
 onChange={() => toggleSelect(doc)}
 />
 </td>
 <td className="px-4 py-4 flex items-center gap-3">
 <FileText className="w-4 h-4 text-ink-muted" />
 {doc}
 </td>
 <td className="px-4 py-4 text-right">
 <button onClick={() => handleDelete(doc)} className="text-ink-muted hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all p-1 cursor-pointer">
 <Trash2 className="w-4 h-4" />
 </button>
 </td>
 </tr>
 ))}
 </tbody>
 </table>
 </div>
 )}
 </div>
 <Modal isOpen={!!modal} onClose={() => setModal(null)} {...modal} isAlert={modal?.type === "alert"} />
 </div>
 );
}

