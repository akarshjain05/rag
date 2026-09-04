import { useRef, useState } from "react";

export default function Sidebar({ documents, totalChunks, onUpload, isUploading, onDeleteDocument }) {
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
          style={{ padding: "2px 6px", fontSize: "11px", cursor: "pointer", background: "var(--accent-hybrid)", color: "white", border: "none", borderRadius: "3px" }}
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
            <li className="doc-item" key={name} style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
              <div style={{ wordBreak: "break-all" }}>
                <span className="doc-item__mark">&bull;</span>
                {name}
              </div>
              <button
                onClick={() => onDeleteDocument(name)}
                title={`Delete ${name}`}
                style={{ 
                  background: "transparent", 
                  border: "none", 
                  color: "var(--danger)", 
                  cursor: "pointer", 
                  fontSize: "14px", 
                  lineHeight: "1",
                  padding: "0 4px",
                  opacity: 0.7,
                  marginTop: "2px"
                }}
                onMouseOver={(e) => e.target.style.opacity = 1}
                onMouseOut={(e) => e.target.style.opacity = 0.7}
              >
                &times;
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
