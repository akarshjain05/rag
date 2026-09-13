with open("apps/web/src/views/ChatView.tsx", "r") as f:
    text = f.read()

target = r"""    const regex = /([^.!?\n]+[.!?]?\s*)(\[\d+\])/g;
    let lastIndex = 0;
    const result = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        result.push(text.substring(lastIndex, match.index));
      }
      const phrase = match[1];
      const citeMatch = match[2].match(/\[(\d+)\]/);
      const citeNum = citeMatch ? citeMatch[1] : '';
      result.push(
        <span key={match.index} className="inline group">
          {phrase}
          <span>
            <sup className="text-accent font-mono ml-[2px]">{citeNum}</sup>
          </span>
        </span>
      );
      lastIndex = regex.lastIndex;
    }"""

replacement = r"""    const regex = /([^.!?\n]+[.!?]?\s*)((?:\[\d+\]\s*)+)/g;
    let lastIndex = 0;
    const result = [];
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        result.push(text.substring(lastIndex, match.index));
      }
      const phrase = match[1];
      const citeMatches = Array.from(match[2].matchAll(/\[(\d+)\]/g));
      const citeNums = citeMatches.map(m => m[1]);
      result.push(
        <span key={match.index} className="inline group">
          {phrase}
          <span>
            {citeNums.map((num, idx) => (
              <sup key={idx} className="text-accent font-mono ml-[2px]">{num}</sup>
            ))}
          </span>
        </span>
      );
      lastIndex = regex.lastIndex;
    }"""

text = text.replace(target, replacement)
with open("apps/web/src/views/ChatView.tsx", "w") as f:
    f.write(text)

