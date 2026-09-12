// @ts-nocheck
// @ts-nocheck

import { createPortal } from "react-dom";

import React, { useState, useEffect } from 'react';
import { fetchConversations, fetchDocuments, deleteDocument, ingest, ask } from '../../lib/api';
import { MessageCircle, Folder, Clock, BarChart, Settings, FileText, ArrowRight, X, Trash2, Check, ThumbsUp, ThumbsDown, LogOut, Moon, Sun, Menu, MoreHorizontal, Copy } from 'lucide-react';




export default function Modal({ isOpen, onClose, title, message, onConfirm, confirmText, isAlert }: any) {
 if (!isOpen) return null;
 return (
 <div className="fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4">
 <div className="bg-surface-sunken border border-border rounded-sm max-w-md w-full p-6 ">
 <h3 className="text-lg font-medium text-ink mb-2">{title}</h3>
 <p className="text-ink-secondary mb-6">{message}</p>
 <div className="flex justify-end gap-3">
 {!isAlert && (
 <button
 onClick={onClose}
 className="px-4 py-2 rounded-sm text-sm font-medium text-ink hover:bg-gray-100 transition-colors"
 >
 Cancel
 </button>
 )}
 <button
 onClick={() => { if (onConfirm) onConfirm(); onClose(); }}
 className={`px-4 py-2 rounded-sm text-sm font-medium text-ink transition-colors ${isAlert ? 'bg-transparent border border-accent text-accent hover:bg-accent-tint' : 'bg-transparent border border-accent text-accent hover:bg-accent-tint'}`}
 >
 {confirmText || 'Confirm'}
 </button>
 </div>
 </div>
 </div>
 );
}

