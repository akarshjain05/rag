import re
with open("README.md", "r") as f:
    text = f.read()
    
pitch = """## 🚀 Project Overview

**Architected a modular RAG pipeline using FastAPI and Qdrant. Implemented hybrid search with cross-encoder reranking, proactive query normalization, temporal RAG, and OpenTelemetry observability to eliminate hallucinations and track pipeline latency.**

This project demonstrates a production-ready, enterprise-grade architecture that prioritizes cost-efficiency, software engineering rigor, and observability. It replaces naive "LangChain PDF Chatbot" patterns with deterministic routing, semantic caching, and a tiered LLM architecture.

"""

text = re.sub(r"## 🚀 Project Overview\n\n(.*?)\n\n", pitch, text, flags=re.DOTALL)
if "Architected a modular RAG pipeline" not in text:
    text = text.replace("## 🚀 Project Overview", pitch)

with open("README.md", "w") as f:
    f.write(text)
