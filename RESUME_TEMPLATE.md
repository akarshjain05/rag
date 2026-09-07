# Resume Bullet Points for RAG Portfolio

When adding this project to your resume or LinkedIn, avoid generic "tool-only" bullet points (e.g., "Built a RAG chatbot using FastAPI and Qdrant"). Instead, use these infrastructure-focused bullet points to prove systems thinking and production readiness:

- **Architected a modular RAG pipeline** via FastAPI, isolating retrieval and generation logic to enable independent horizontal scaling of compute and database resources.
- **Optimized vector search transport latency** by implementing gRPC over HTTP/2 and establishing persistent connection pooling during the FastAPI application lifespan.
- **Designed an enterprise-ready deployment topology**, co-locating stateless web workers and the Qdrant managed cluster in the same AWS region to eliminate cross-zone latency and egress costs.
- **Engineered a zero-cost, tiered LLM architecture**, utilizing local ONNX cross-encoder reranking and routing proactive normalization to high-speed Tier 3 models to drop TTFT (Time To First Token).
- **Integrated comprehensive observability and tracing**, instrumenting the pipeline with OpenTelemetry to track component execution latency, token utilization, and retrieval confidence scores.

## Pitching the Project
During interviews, emphasize that this project was built to solve the "hidden 90%" of AI engineering: the infrastructure required to make models run reliably and cost-effectively at scale.
