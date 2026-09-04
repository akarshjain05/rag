// Same-origin relative paths throughout: Vite's dev server proxies /v1 and
// /health to the API (see vite.config.js), and nginx does the equivalent in
// the built/containerized version (see Dockerfile + nginx.conf). No CORS
// config and no build-time API URL to get wrong.


async function request(path, options = {}, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(path, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
      });
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const body = await res.json();
          detail = body.detail || JSON.stringify(body);
        } catch {
          /* ignore */
        }
        // Only retry on 5xx or network errors
        if (res.status >= 500 && i < retries - 1) {
          await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i))); // exponential backoff
          continue;
        }
        throw new Error(`${res.status}: ${detail}`);
      }
      return await res.json();
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      if (i === retries - 1) throw err;
      await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
    }
  }
}


export function fetchHealth() {
  return request("/health");
}

export function fetchDocuments() {
  return request("/v1/documents");
}

export function ask({ signal, question, conversationId = null, verifyCitations = null, topK = 5, chunkingStrategy = null, compareDenseOnly = false, imageUrl = null }) {
  return request("/v1/ask", {
    method: "POST",
    signal,
    body: JSON.stringify({
      question,
      conversation_id: conversationId || undefined,
      verify_citations: verifyCitations ?? undefined,
      top_k: topK,
      chunking_strategy: chunkingStrategy,
      compare_dense_only: compareDenseOnly,
      image_url: imageUrl || undefined,
    }),
  });
}

export async function ingest(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  
  const res = await fetch("/v1/ingest", {
    method: "POST",
    signal,
    body: formData,
  });
  
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}
