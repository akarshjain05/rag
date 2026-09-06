// Same-origin relative paths throughout: Vite's dev server proxies /v1 and
// /health to the API (see vite.config.js), and nginx does the equivalent in
// the built/containerized version (see Dockerfile + nginx.conf). No CORS
// config and no build-time API URL to get wrong.


async function request(path, options = {}, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const apiKey = import.meta.env.VITE_API_KEY || localStorage.getItem("apiKey");
      const headers = { 
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
        ...(options.headers || {}) 
      };
      const res = await fetch(path, {
        ...options,
        headers,
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

export function ask({ signal, question, conversationId = null, verifyCitations = null, topK = 5, chunkingStrategy = null, compareDenseOnly = false, imageUrl = null, documentFilter = null }) {
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
      document_filter: documentFilter?.length ? documentFilter : undefined,
    }),
  });
}


export async function ingest(files, onProgress, signal) {
  // Size check for large files (>1MB)
  const isLarge = Array.from(files).some((f: any) => f.size > 1024 * 1024);
  
  if (isLarge) {
    if (onProgress) onProgress('0 chunks', "Initiating async job for large files...");
    const results = [];
    
    // Process one by one for large files
    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      
      const apiKey = import.meta.env.VITE_API_KEY || localStorage.getItem("apiKey");
      const res = await fetch("/v1/ingest/large", {
        headers: apiKey ? { "X-API-Key": apiKey } : {},
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) throw new Error(`${res.status}: Failed to start async job`);
      const { job_id } = await res.json();
      
      // Poll
      while (true) {
        if (signal?.aborted) {
            await fetch(`/v1/ingest/jobs/${job_id}`, { method: 'DELETE', headers: apiKey ? { "X-API-Key": apiKey } : {} }).catch(() => {});
            throw new DOMException("Aborted", "AbortError");
        }
        await new Promise(r => setTimeout(r, 2000));
        const pollRes = await fetch(`/v1/ingest/jobs/${job_id}`, {
          headers: apiKey ? { "X-API-Key": apiKey } : {}
        });
        if (!pollRes.ok) continue; // Skip this tick if the API is temporarily unavailable
        const statusData = await pollRes.json();
        
        if (statusData.status === "PROGRESS" && onProgress) {
          onProgress((statusData.info?.chunks_processed || 0) + ' chunks', `Indexing ${file.name}...`);
        } else if (statusData.status === "SUCCESS") {
          results.push(statusData.info);
          break;
        } else if (statusData.status === "FAILURE") {
          throw new Error(`Job failed: ${statusData.info}`);
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

  
  if (onProgress) onProgress('0%', "Uploading to server...");
  
  const apiKey = import.meta.env.VITE_API_KEY || localStorage.getItem("apiKey");
  const res = await fetch("/v1/ingest", {
    headers: apiKey ? { "X-API-Key": apiKey } : {},
    method: "POST",
    body: formData,
    signal,
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
    if (signal?.aborted) {
        reader.cancel();
        throw new DOMException("Aborted", "AbortError");
    }
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
            onProgress(data.progress + '%', data.message);
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

export function verifyAuth() {
  return request("/v1/auth", {
    method: "POST",
    headers: import.meta.env.VITE_API_KEY ? { "X-API-Key": import.meta.env.VITE_API_KEY } : (localStorage.getItem("apiKey") ? { "X-API-Key": localStorage.getItem("apiKey") } : {})
  });
}

export function fetchConversations() {
  return request("/v1/conversations", {
    headers: import.meta.env.VITE_API_KEY ? { "X-API-Key": import.meta.env.VITE_API_KEY } : (localStorage.getItem("apiKey") ? { "X-API-Key": localStorage.getItem("apiKey") } : {})
  });
}

export function fetchConversation(id) {
  return request(`/v1/conversations/${encodeURIComponent(id)}`, {
    headers: import.meta.env.VITE_API_KEY ? { "X-API-Key": import.meta.env.VITE_API_KEY } : (localStorage.getItem("apiKey") ? { "X-API-Key": localStorage.getItem("apiKey") } : {})
  });
}

export function submitFeedback(conversationId, turnIndex, isPositive) {
  return request(`/v1/conversations/${encodeURIComponent(conversationId)}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ turn_index: turnIndex, is_positive: isPositive }),
  });
}

export function fetchInsights() {
  return request('/v1/insights');
}
