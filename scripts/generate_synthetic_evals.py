import argparse
import json
from pathlib import Path
from rag_api.core.settings import get_settings
from rag_api.adapters.llm.llm_client import build_llm_client

def generate_synthetic_qa(llm_client, text_chunk: str, num_questions: int = 3):
    # Prompt the LLM to generate hard, realistic questions based on the chunk
    prompt = f"""
    You are an expert QA engineer. Based on the following document chunk, generate {num_questions} realistic, 
    highly specific questions that a user might ask. For each question, provide the golden answer based *only* on the text.
    Include one 'lookup' question, one 'multi-hop' style question requiring synthesis, and one 'ambiguous' question.
    
    Document Chunk:
    {text_chunk}
    
    Output JSON format:
    [
      {{"question": "...", "golden_answer": "...", "category": "lookup"}}
    ]
    """
    
    response = llm_client.generate(prompt)
    try:
        # Strip markdown code blocks if present
        content = response.answer.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Failed to parse LLM response: {e}")
        return []

def main():
    settings = get_settings()
    llm = build_llm_client(
        provider=settings.llm_provider,
        model=settings.anthropic_model if settings.llm_provider == "anthropic" else settings.openai_llm_model,
        api_key=settings.anthropic_api_key if settings.llm_provider == "anthropic" else settings.openai_api_key,
        base_url=settings.openai_base_url if settings.llm_provider == "openai" else None
    )
    
    corpus_dir = Path("eval/vellumiq_corpus")
    out_file = Path("eval/vellumiq_qa_expanded.json")
    
    all_qa = []
    
    # In a real run, you'd chunk the corpus. Here we just read the raw files for simplicity.
    for p in corpus_dir.glob("*.txt"):
        text = p.read_text()
        print(f"Processing {p.name}...")
        qa_pairs = generate_synthetic_qa(llm, text[:4000], num_questions=3) # simplistic 4k char crop
        all_qa.extend(qa_pairs)
        
    with open(out_file, "w") as f:
        json.dump(all_qa, f, indent=2)
        
    print(f"Generated {len(all_qa)} synthetic QA pairs and saved to {out_file}")

if __name__ == "__main__":
    main()
