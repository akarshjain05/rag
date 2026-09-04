import { describe, it, expect } from 'vitest';
import { splitOnCitations } from './AnswerPanel';

describe('splitOnCitations', () => {
  it('splits text without citations into a single text segment', () => {
    expect(splitOnCitations("Just some text.")).toEqual([
      { type: "text", value: "Just some text." }
    ]);
  });

  it('extracts a single citation', () => {
    expect(splitOnCitations("The answer is 42 [1].")).toEqual([
      { type: "text", value: "The answer is 42 " },
      { type: "citation", value: 1 },
      { type: "text", value: "." }
    ]);
  });

  it('handles multiple adjacent citations', () => {
    expect(splitOnCitations("Found in [1][2]")).toEqual([
      { type: "text", value: "Found in " },
      { type: "citation", value: 1 },
      { type: "citation", value: 2 }
    ]);
  });

  it('handles empty string', () => {
    expect(splitOnCitations("")).toEqual([]);
  });
});
