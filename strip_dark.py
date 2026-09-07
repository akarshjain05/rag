import re

with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

# Remove all dark: class names
text = re.sub(r'\bdark:[^\s\'"]+\b', '', text)
# Clean up multiple spaces that might result from removal
text = re.sub(r'  +', ' ', text)

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)
