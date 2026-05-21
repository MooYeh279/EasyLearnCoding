import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

// Mock heavy dependencies BEFORE importing the component
vi.mock('@monaco-editor/react', () => ({
  Editor: () => React.createElement('div', { 'data-testid': 'monaco-editor' }, 'Monaco'),
}));

vi.mock('react-syntax-highlighter', () => ({
  Prism: ({ children }: any) => React.createElement('pre', { 'data-testid': 'syntax-highlighter' }, children),
}));

vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  oneDark: {},
}));

vi.mock('../MarkdownRenderer', () => ({
  default: ({ content }: any) => React.createElement('div', { 'data-testid': 'markdown-renderer' }, content),
}));

vi.mock('../../api/client', () => ({
  api: {
    runCodeStream: vi.fn(),
  },
}));

vi.mock('../../context/LangContext', () => ({
  useContentLang: () => ({
    t: (key: string) => key,
    contentLang: 'zh',
    setContentLang: vi.fn(),
  }),
}));

// Now import the component
import NotebookCellComp from '../NotebookCell';
import type { NotebookCell } from '../../types';

function createCell(overrides: Partial<NotebookCell> = {}): NotebookCell {
  if (overrides.type === 'code') {
    return {
      id: 'test-1',
      type: 'code',
      language: 'python',
      code: 'print(1)',
      output: null,
      ...overrides,
    } as NotebookCell;
  }
  return {
    id: 'test-1',
    type: 'markdown',
    content: '# Hello World',
    ...overrides,
  } as NotebookCell;
}

const defaultProps = {
  index: 0,
  total: 1,
  onChange: vi.fn(),
  onDelete: vi.fn(),
  onMove: vi.fn(),
};

describe('NotebookCellComp', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders markdown cell content', () => {
    const cell = createCell({ type: 'markdown', content: '# Test' });
    render(React.createElement(NotebookCellComp, { cell, ...defaultProps }));
    expect(screen.getByTestId('markdown-renderer')).toBeTruthy();
  });

  it('renders code cell with syntax highlighter', () => {
    const cell = createCell({ type: 'code', language: 'python', code: 'print(1)', output: null });
    render(React.createElement(NotebookCellComp, { cell, ...defaultProps }));
    expect(screen.getByTestId('syntax-highlighter')).toBeTruthy();
  });

  it('calls onDelete when delete button clicked', () => {
    const onDelete = vi.fn();
    const cell = createCell();
    render(React.createElement(NotebookCellComp, { cell, ...defaultProps, onDelete }));
    const buttons = screen.getAllByRole('button');
    // Find the button with DeleteOutlined icon (anticon-delete class nested deeper)
    const deleteBtn = buttons.find(b => b.querySelector('.anticon-delete'));
    expect(deleteBtn).toBeTruthy();
    if (deleteBtn) {
      fireEvent.click(deleteBtn);
      expect(onDelete).toHaveBeenCalledWith('test-1');
    }
  });

  it('shows move up button disabled for first item', () => {
    const cell = createCell();
    render(React.createElement(NotebookCellComp, { cell, ...defaultProps, index: 0, total: 3 }));
    const buttons = screen.getAllByRole('button');
    const upBtn = buttons.find(b => b.querySelector('.anticon-up'));
    expect(upBtn).toBeTruthy();
    if (upBtn) {
      expect((upBtn as HTMLButtonElement).disabled).toBe(true);
    }
  });

  it('shows move down button disabled for last item', () => {
    const cell = createCell();
    render(React.createElement(NotebookCellComp, { cell, ...defaultProps, index: 2, total: 3 }));
    const buttons = screen.getAllByRole('button');
    const downBtn = buttons.find(b => b.querySelector('.anticon-down'));
    expect(downBtn).toBeTruthy();
    if (downBtn) {
      expect((downBtn as HTMLButtonElement).disabled).toBe(true);
    }
  });
});
