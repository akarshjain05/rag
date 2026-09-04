// Same-origin relative paths throughout: Vite's dev server proxies /v1 and
// /health to the API (see vite.config.js), and nginx does the equivalent in
// the built/containerized version (see Dockerfile + nginx.conf). No CORS
// config and no build-time API URL to get wrong.

async function request(path, options = {}) {
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
      /* response wasn't JSON -- fall back to statusText */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export function fetchHealth() {
  return request("/health");
}

export function fetchDocuments() {
  return request("/v1/documents");
}

export function ask({ question, topK = 5, chunkingStrategy = null, compareDenseOnly = false, imageUrl = null }) {
  return request("/v1/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
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
