import type { NotebookCell } from '../types';

export function parseCells(raw: string): NotebookCell[] {
  if (!raw || raw === '[]') return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export function generateId(): string {
  return crypto.randomUUID().slice(0, 8);
}

export function cellsToMarkdown(cells: NotebookCell[]): string {
  return cells.map((c) => {
    if (c.type === 'markdown') return c.content;
    return '```' + c.language + '\n' + c.code + '\n```';
  }).join('\n\n');
}

export function downloadMarkdown(filename: string, md: string) {
  const blob = new Blob([md], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename.endsWith('.md') ? filename : filename + '.md';
  a.click();
  URL.revokeObjectURL(url);
}
