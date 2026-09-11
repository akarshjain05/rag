with open("apps/api/src/rag_api/adapters/llm/llm_client.py", "r") as f:
    lines = f.readlines()
with open("apps/api/src/rag_api/adapters/llm/llm_client.py", "w") as f:
    # Delete the broken inserted `generate_with_metrics`
    f.writelines(lines[:170])
    f.writelines(lines[220:])
