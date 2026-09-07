with open("apps/web/src/index.css", "r") as f:
    text = f.read()

text = text.replace(
    "html, body, #root {\\n  background-color: var(--color-canvas);\\n  color: var(--color-ink);\\n  font-family: var(--font-sans);\\n  height: 100%;\\n}",
    "html, body, #root {\\n  background-color: var(--color-canvas);\\n  color: var(--color-ink);\\n  font-family: var(--font-sans);\\n  height: 100%;\\n  overflow: hidden;\\n}\\n\\n* {\\n  border-color: var(--color-border);\\n}"
)

with open("apps/web/src/index.css", "w") as f:
    f.write(text)
