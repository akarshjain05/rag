import os

replacements = {
    "vellumiq_qa": "vellumiq_qa",
    "vellumiq_corpus": "vellumiq_corpus",
    "vellumiq_baseline": "vellumiq_baseline",
    "vellumiq_sla": "vellumiq_sla",
    "vellumiq-rag": "vellumiq-rag",
    "Vellumiq": "Vellumiq"
}

def process_file(filepath):
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except Exception:
        return
    
    new_content = content
    for old, new in replacements.items():
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, "w") as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk("."):
    if ".git" in root or "node_modules" in root or "__pycache__" in root or ".venv" in root:
        continue
    for f in files:
        if f.endswith(".pdf") or f.endswith(".png") or f.endswith(".jpg"):
            continue
        process_file(os.path.join(root, f))
