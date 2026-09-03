export default function Sidebar({ documents, totalChunks }) {
  return (
    <aside className="sidebar">
      <p className="sidebar__label">Index &middot; {documents.length} docs, {totalChunks} chunks</p>
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
