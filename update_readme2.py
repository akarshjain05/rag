with open("README.md", "r") as f:
    text = f.read()

header = """# Enterprise RAG Pipeline (Temporal Hybrid Search)

**Architected a modular RAG pipeline using FastAPI and Qdrant. Implemented hybrid search with cross-encoder reranking, proactive query normalization, temporal versioning, and observability to eliminate hallucinations and track pipeline latency.**

## 🌟 The "Zero-Cost" Pro Stack
- **Database**: Qdrant running locally via Docker (Rust-based, native Hybrid Search).
- **Embeddings & Reranking**: FastEmbed (ONNX runtime) executing Jina embeddings and cross-encoder reranking directly on CPU. Zero API costs.
- **LLM Routing**: Tiered architecture routing proactive normalization to cheaper/faster models (e.g., Claude 3.5 Haiku) to drop TTFT.
- **UI**: React/Vite interface featuring a Gemini-style chat history, dynamic explicit citations, and transparent confidence logging.
- **Observability**: Fully instrumented with OpenTelemetry and Prometheus to track component execution latency and token metrics.

## 🚀 Quickstart (Single-Command Setup)

```bash
# 1. Copy the example environment file
cp .env.example .env

# 2. Add your LLM API Key to .env
# ANTHROPIC_API_KEY=your_key_here

# 3. Spin up the entire stack (API, Frontend, Qdrant, Redis, MinIO)
docker compose up -d --build
```
"""

# Replace the beginning of the file
import re
new_text = re.sub(r"# RAG Pipeline with Hybrid Search Over Internal Docs.*?\n## Architecture", header + "\n## Architecture", text, flags=re.DOTALL)
with open("README.md", "w") as f:
    f.write(new_text)
