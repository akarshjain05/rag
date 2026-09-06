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


export async function ingest(files, onProgress) {
  // Size check for large files (>1MB)
  const isLarge = Array.from(files).some((f: any) => f.size > 1024 * 1024);
  
  if (isLarge) {
    if (onProgress) onProgress(0, "Initiating async job for large files...");
    const results = [];
    
    // Process one by one for large files
    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      
      const res = await fetch("/v1/ingest/large", {
        headers: { "X-API-Key": "sk-default-test-key" },
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) throw new Error(`${res.status}: Failed to start async job`);
      const { job_id } = await res.json();
      
      // Poll
      while (true) {
        await new Promise(r => setTimeout(r, 2000));
        const pollRes = await fetch(`/v1/ingest/jobs/${job_id}`, {
          headers: { "X-API-Key": "sk-default-test-key" }
        });
        const statusData = await pollRes.json();
        
        if (statusData.status === "PROGRESS" && onProgress) {
          onProgress(statusData.meta?.chunks_processed || 0, `Indexing ${file.name}...`);
        } else if (statusData.status === "SUCCESS") {
          results.push(statusData.result);
          break;
        } else if (statusData.status === "FAILURE") {
          throw new Error(`Job failed: ${statusData.meta}`);
        }
      }
    }
    return { reports: results };
  }

  // Original sync/SSE path for small files
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  
  if (onProgress) onProgress(0, "Uploading to server...");
  
  const res = await fetch("/v1/ingest", {
    headers: {
      "X-API-Key": "sk-default-test-key"
    },
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
  
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let result = null;
  let buffer = "";
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || "";
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const jsonStr = line.substring(6);
        let data = null;
        try {
          data = JSON.parse(jsonStr);
        } catch(e) {}
        if (data) {
          if (data.progress !== undefined && onProgress) {
            onProgress(data.progress, data.message);
          }
          if (data.error) {
            throw new Error(data.error);
          }
          if (data.reports) {
            result = data;
          }
        }
      }
    }
  }
  
  return result;
}

export function deleteDocument(sourceDocument) {
  return request(`/v1/documents/${encodeURIComponent(sourceDocument)}`, {
    method: "DELETE",
  });
}
