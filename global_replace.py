with open("apps/web/src/App.tsx", "r") as f:
    text = f.read()

replacements = {
    "bg-gray-50 dark:bg-[#141414]": "bg-[var(--color-surface)]",
    "bg-[#FAFAFA] dark:bg-[#0A0A0A]": "bg-[var(--color-surface-sunken)]",
    "bg-white dark:bg-[#0A0A0A]": "bg-[var(--color-surface-card)]",
    "bg-white dark:bg-white/5": "bg-[var(--color-surface-card)]",
    "bg-gray-50 dark:bg-white/5": "bg-[var(--color-surface-card)]",
    "bg-gray-100 dark:bg-white/10": "bg-[var(--color-surface-card)]",
    "border-gray-200 dark:border-white/10": "border-[var(--color-border)]",
    "border-gray-300 dark:border-gray-600": "border-[var(--color-border)]",
    "text-gray-900 dark:text-white": "text-[var(--color-ink)]",
    "text-gray-900": "text-[var(--color-ink)]",
    "text-gray-800": "text-[var(--color-ink)]",
    "text-gray-700": "text-[var(--color-ink)]",
    "text-gray-600 dark:text-gray-300": "text-[var(--color-ink)]",
    "text-gray-500 dark:text-gray-400": "text-[var(--color-ink-secondary)]",
    "text-gray-500": "text-[var(--color-ink-secondary)]",
    "text-gray-400": "text-[var(--color-ink-muted)]",
    "rounded-2xl": "rounded-sm",
    "rounded-xl": "rounded-sm",
    "rounded-lg": "rounded-sm",
    "shadow-sm": "",
    "shadow-md": "",
    "shadow-2xl": "",
    "shadow-lg": "",
    "bg-blue-600 hover:bg-blue-700 text-white": "border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent-tint)]",
    "bg-blue-600 text-white rounded-lg hover:bg-blue-700": "border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent-tint)] rounded-sm",
    "bg-blue-600 rounded-lg text-white": "border border-[var(--color-accent)] text-[var(--color-accent)] rounded-sm",
    "bg-red-600 hover:bg-red-700 text-white": "border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent-tint)]",
    "bg-red-600 hover:bg-red-700": "bg-transparent border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent-tint)]",
    "bg-blue-600 hover:bg-blue-700": "bg-transparent border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent-tint)]",
    "text-white": "text-[var(--color-ink)]", # Some buttons might be left with text-white
}

for old, new in replacements.items():
    text = text.replace(old, new)

with open("apps/web/src/App.tsx", "w") as f:
    f.write(text)
