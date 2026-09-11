import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from rag_api.core.settings import get_settings
from rag_api.adapters.vectorstore.embeddings import build_embedding_client
from rag_api.domain.generation.generation import AnswerGenerator
from rag_api.adapters.llm.llm_client import build_llm_client
from rag_api.adapters.storage.loaders import SUPPORTED_EXTENSIONS
from rag_api.domain.models import ChunkingStrategy
from rag_api.services.ingest_service import IngestionPipeline
from rag_api.domain.retrieval.retrieval import HybridRetriever
from rag_api.adapters.vectorstore.vector_store import VectorStore
from rag_api.domain.generation.verification import CitationVerifier
from eval.golden_dataset import load_golden_dataset

DEFAULT_DATASET = Path(__file__).parent / "golden_qa.json"
DEFAULT_CORPUS = Path(__file__).parent / "golden_corpus"

def main():
    parser = argparse.ArgumentParser(description="Run Ragas Eval")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--chunking-strategy", default="structure_aware", choices=[s.value for s in ChunkingStrategy])
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    settings = get_settings()
    
    # Initialize our app's core components
    embedding_client = build_embedding_client(
        settings.embedding_provider,
        openai_model=settings.openai_embedding_model,
        openai_api_key=settings.openai_api_key,
        local_model=settings.local_embedding_model,
    )
    llm_client = build_llm_client(
        settings.llm_provider,
        model=settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_llm_model,
        api_key=settings.anthropic_api_key if settings.llm_provider == "anthropic" else settings.openai_api_key,
    )

    examples = load_golden_dataset(args.dataset)
    doc_paths = [p for p in sorted(args.docs_dir.iterdir()) if p.suffix.lower() in SUPPORTED_EXTENSIONS]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        vector_store = VectorStore(tmp_path / "chroma", "eval_collection", dense_dimension=embedding_client.dimension)
        pipeline = IngestionPipeline(embedding_client, vector_store)
        retriever = HybridRetriever(
            embedding_client, vector_store, dense_top_k=args.top_k * 2, sparse_top_k=args.top_k * 2
        )
        generator = AnswerGenerator(
            llm_client,
            mode="llm",
            citation_verifier=CitationVerifier(llm_client),
            low_confidence_threshold=settings.low_confidence_threshold,
        )

        print(f"Ingesting {len(doc_paths)} document(s)...")
        reports = pipeline.ingest_files(doc_paths, strategy=ChunkingStrategy(args.chunking_strategy))
        print(f"  {sum(r.chunks_inserted for r in reports)} chunks inserted")

        questions = []
        answers = []
        contexts = []
        ground_truths = []

        print(f"\nGenerating answers for {len(examples)} examples...")
        for i, example in enumerate(examples):
            print(f"  [{i+1}/{len(examples)}] {example.question}")
            # RAG pipeline
            chunks = retriever.retrieve(example.question, top_k=args.top_k, chunking_strategy=args.chunking_strategy)
            gen_result = generator.generate(example.question, chunks)
            
            # Formatting for Ragas
            questions.append(example.question)
            answers.append(gen_result.answer)
            contexts.append([c.text for c in chunks])
            ground_truths.append(example.golden_answer)

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths
        }
        dataset = Dataset.from_dict(data)

        print("\nEvaluating with Ragas...")
        
        # Determine langchain models for ragas
        eval_llm = ChatOpenAI(model=os.environ.get("OPENAI_LLM_MODEL", "gpt-3.5-turbo"))
        eval_embeddings = OpenAIEmbeddings(model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
        
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=eval_llm,
            embeddings=eval_embeddings
        )

        print("\nRagas Evaluation Results:")
        print(result)

        # Output to json
        out_file = "eval/ragas_baseline.json"
        with open(out_file, "w") as f:
            # result is a dictionary-like object with pandas dataframe capabilities, 
            # we can just convert to dict
            json.dump(dict(result), f, indent=2)
        print(f"\nSaved Ragas baseline to {out_file}")

if __name__ == "__main__":
    main()
