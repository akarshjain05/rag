import { useRef, useState } from "react";

export default function Sidebar({ documents, totalChunks, onUpload, isUploading }) {
  const fileInputRef = useRef(null);

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  async function handleFileChange(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    await onUpload(files);
    e.target.value = ""; // reset
  }

  return (
    <aside className="sidebar">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
        <p className="sidebar__label" style={{ margin: 0 }}>Index &middot; {documents.length} docs, {totalChunks} chunks</p>
        <button 
          onClick={handleUploadClick} 
          disabled={isUploading}
          style={{ padding: "2px 6px", fontSize: "11px", cursor: "pointer", background: "var(--accent-color)", color: "white", border: "none", borderRadius: "3px" }}
        >
          {isUploading ? "Uploading..." : "Upload Files"}
        </button>
        <input 
          type="file" 
          multiple 
          ref={fileInputRef} 
          style={{ display: "none" }} 
          onChange={handleFileChange}
        />
      </div>

      {documents.length === 0 ? (
        <p className="doc-item doc-item--dim">nothing ingested yet</p>
      ) : (
        <ul className="doc-list">
          {documents.map((name) => (
            <li className="doc-item" key={name}>
              <span className="doc-item__mark">&bull;</span>
              {name}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
