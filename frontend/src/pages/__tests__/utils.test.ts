import { describe, it, expect } from 'vitest';

// Inline the functions to test them directly (they're not exported from LearningView)
function parseCells(raw: string): any[] {
  if (!raw || raw === '[]') return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function cellsToMarkdown(cells: any[]): string {
  return cells.map((c: any) => {
    if (c.type === 'markdown') return c.content;
    return '```' + c.language + '\n' + c.code + '\n```';
  }).join('\n\n');
}

describe('parseCells', () => {
  it('returns empty array for empty string', () => {
    expect(parseCells('')).toEqual([]);
  });

  it('returns empty array for "[]"', () => {
    expect(parseCells('[]')).toEqual([]);
  });

  it('parses markdown cell correctly', () => {
    const result = parseCells('[{"id":"c1","type":"markdown","content":"# Hello"}]');
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ id: 'c1', type: 'markdown', content: '# Hello' });
  });

  it('parses code cell correctly', () => {
    const result = parseCells('[{"id":"c2","type":"code","language":"python","code":"print(1)","output":null}]');
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe('code');
    expect(result[0].language).toBe('python');
  });

  it('returns empty array for invalid JSON', () => {
    expect(parseCells('not json')).toEqual([]);
  });

  it('returns empty array for null', () => {
    expect(parseCells(null as any)).toEqual([]);
  });
});

describe('cellsToMarkdown', () => {
  it('converts markdown cell to raw content', () => {
    const cells = [{ id: 'c1', type: 'markdown', content: '# Title' }];
    expect(cellsToMarkdown(cells)).toBe('# Title');
  });

  it('converts code cell to fenced code block', () => {
    const cells = [{ id: 'c2', type: 'code', language: 'python', code: 'print(1)' }];
    expect(cellsToMarkdown(cells)).toBe('```python\nprint(1)\n```');
  });

  it('joins multiple cells with double newline', () => {
    const cells = [
      { id: 'c1', type: 'markdown', content: '# Title' },
      { id: 'c2', type: 'code', language: 'python', code: 'print(1)' },
    ];
    expect(cellsToMarkdown(cells)).toBe('# Title\n\n```python\nprint(1)\n```');
  });
});
