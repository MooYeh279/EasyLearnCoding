import { useState, useRef, useCallback, lazy, Suspense, memo, useEffect } from 'react';
import { Button, Tooltip, Input, Spin, Select } from 'antd';
import { PlayCircleOutlined, EditOutlined, DeleteOutlined, UpOutlined, DownOutlined, CopyOutlined, CheckOutlined, CloseCircleOutlined, SwapOutlined, CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import MarkdownRenderer from './MarkdownRenderer';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import type { NotebookCell, CellOutput } from '../types';

// Eagerly preload Monaco to eliminate flicker when clicking code cells
const MonacoEditor = lazy(() => import('@monaco-editor/react').then(m => ({ default: m.Editor })));

const LANG_OPTIONS = [
  { value: 'python',     label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'c',          label: 'C' },
  { value: 'cpp',        label: 'C++' },
  { value: 'bash',       label: 'Bash' },
  { value: 'cmd',        label: 'CMD' },
  { value: 'powershell', label: 'PowerShell' },
  { value: 'txt',        label: 'Plain Text' },
];

/* ── Design tokens ── */
const C = {
  primary:    '#5b5feb',
  success:    '#10b981',
  error:      '#ef4444',
  text:       '#1e1e24',
  textSec:    '#6b7280',
  border:     '#e8e8ed',
  toolbarBg:  '#f8f9fb',
  codeBg:     '#1e1e2e',
  radius:     8,
};

interface Props {
  cell: NotebookCell;
  index: number;
  total: number;
  onChange: (id: string, updates: Partial<NotebookCell>) => void;
  onDelete: (id: string) => void;
  onMove: (id: string, direction: 'up' | 'down') => void;
  onInsertAbove?: () => void;
  onInsertBelow?: () => void;
  onEditStart?: (id: string) => void;
  onEditCancel?: (id: string) => void;
}

const NotebookCellComp = memo(function NotebookCellComp({ cell, index, total, onChange, onDelete, onMove, onInsertAbove, onInsertBelow, onEditStart, onEditCancel }: Props) {
  const { t } = useContentLang();
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);
  const [hovered, setHovered] = useState(false);
  const editorRef = useRef<any>(null);
  const abortRef = useRef<AbortController | null>(null);
  const preloadedRef = useRef(false);

  // Refs to hold latest callbacks so Monaco keybindings don't go stale
  const saveEditRef = useRef<() => void>(() => {});
  const handleRunRef = useRef<() => void>(() => {});

  const isMd = cell.type === 'markdown';
  const isTxt = cell.type === 'code' && cell.language === 'txt';
  const canRun = cell.type === 'code' && cell.language !== 'txt';

  // Preload Monaco on mount so it's cached when user clicks to edit — eliminates flicker
  useEffect(() => {
    if (isMd || preloadedRef.current) return;
    preloadedRef.current = true;
    const timer = setTimeout(() => {
      import('@monaco-editor/react');
    }, 300);
    return () => clearTimeout(timer);
  }, [isMd]);

  const handleCopy = async () => {
    const text = isMd ? cell.content : cell.code;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const startEdit = () => {
    setEditText(isMd ? cell.content : cell.code);
    setEditing(true);
    onEditStart?.(cell.id);
  };

  const saveEdit = useCallback(() => {
    setEditing(false);
    if (isMd) {
      onChange(cell.id, { content: editText });
    } else {
      const currentCode = editorRef.current?.getValue?.() ?? editText;
      onChange(cell.id, { code: currentCode });
    }
  }, [isMd, editText, cell.id, onChange]);

  const handleRun = useCallback(async () => {
    if (cell.type !== 'code' || cell.language === 'txt') return;
    if (editing) { setEditText(editorRef.current?.getValue?.() ?? editText); saveEdit(); }
    const codeToRun = editing ? (editorRef.current?.getValue?.() ?? cell.code) : cell.code;
    setRunning(true);
    const output: CellOutput = { stdout: '', stderr: '', exit_code: 0, duration_ms: 0 };
    onChange(cell.id, { output } as any);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      await api.runCodeStream(codeToRun, cell.language, (event, data) => {
        if (event === 'stdout') {
          output.stdout += data.text;
          onChange(cell.id, { output: { ...output } } as any);
        } else if (event === 'stderr') {
          output.stderr += data.text;
          onChange(cell.id, { output: { ...output } } as any);
        } else if (event === 'done') {
          output.exit_code = data.exit_code;
          output.duration_ms = data.duration_ms;
          onChange(cell.id, { output: { ...output } } as any);
        }
      }, ctrl.signal);
    } catch (err: any) {
      output.stderr = err?.message || t('code.execError');
      output.exit_code = 1;
      onChange(cell.id, { output: { ...output } } as any);
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [editing, editText, cell.type, cell.id, cell.type === 'code' ? cell.code : '', cell.type === 'code' ? cell.language : '', onChange, saveEdit, t]);

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleSwitchType = () => {
    if (isMd) {
      onChange(cell.id, { type: 'code', language: 'python', code: cell.content, output: null } as any);
    } else {
      onChange(cell.id, { type: 'markdown', content: cell.code } as any);
    }
  };

  // Keep refs updated so Monaco keybindings always call latest versions
  saveEditRef.current = saveEdit;
  handleRunRef.current = handleRun;

  const handleEditorMount = useCallback((editor: any, monaco: any) => {
    editorRef.current = editor;
    editor.focus();
    editor.addAction({
      id: 'save-and-run',
      label: 'Save and Run',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: () => { saveEditRef.current(); handleRunRef.current(); },
    });
    editor.addAction({
      id: 'save-edit',
      label: 'Save Edit',
      keybindings: [],
      run: () => saveEditRef.current(),
    });
    editor.addAction({
      id: 'cancel-edit',
      label: 'Cancel Edit',
      keybindings: [monaco.KeyCode.Escape],
      run: () => { setEditing(false); onEditCancel?.(cell.id); },
    });
    editor.onDidBlurEditorWidget(() => {
      saveEditRef.current();
    });
  }, []);

  const output = cell.type === 'code' ? cell.output : null;
  const hasOutput = output && (output.stdout || output.stderr);
  const isError = output && output.exit_code !== 0;

  // ── computed styles ──
  const borderColor = running ? C.primary : isError ? C.error : C.border;

  const shadowParts: string[] = [];
  if (hovered) shadowParts.push('0 2px 8px rgba(0,0,0,0.06)');
  if (running) shadowParts.push('0 0 0 2px rgba(91,95,235,0.12)');
  else if (isError) shadowParts.push('0 0 0 2px rgba(239,68,68,0.1)');
  const boxShadow = shadowParts.join(', ') || 'none';

  const iconBtnS: React.CSSProperties = { color: C.textSec, fontSize: 14 };

  // Unified notebook aesthetic: consistent padding, left gutter line, seamless transitions
  return (
    <div
      style={{
        border: `1px solid ${borderColor}`,
        borderRadius: 0,
        marginBottom: 0,
        overflow: 'hidden',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        boxShadow,
        background: '#fff',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* ── Toolbar (hover / editing / running only) ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: (hovered || editing || running) ? 32 : 0,
          padding: (hovered || editing || running) ? '0 10px' : 0,
          background: C.toolbarBg,
          borderBottom: (hovered || editing || running) ? `1px solid ${C.border}` : 'none',
          userSelect: 'none',
          overflow: 'hidden',
          transition: 'height 0.15s ease, padding 0.15s ease',
          opacity: (hovered || editing || running) ? 1 : 0,
        }}
      >
        {/* Left: language / badge */}
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {running ? (
            <span style={{ fontSize: 12, color: C.primary, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <Spin size="small" /> Running...
            </span>
          ) : isMd ? (
            <span style={{ fontSize: 11, color: C.textSec, fontWeight: 500, letterSpacing: '0.02em' }}>
              Markdown
            </span>
          ) : (
            <Select
              size="small"
              value={cell.language}
              onChange={(val) => {
                const updates: any = { language: val, code: cell.code };
                if (val === 'txt') updates.output = null;
                onChange(cell.id, updates);
              }}
              style={{ width: 100, fontSize: 11 }}
              options={LANG_OPTIONS}
            />
          )}
        </div>

        {/* Right: actions (icon-only) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tooltip title={t('code.copy')}>
            <Button
              type="text" size="small"
              icon={copied ? <CheckOutlined style={{ color: C.success, fontSize: 14 }} /> : <CopyOutlined style={iconBtnS} />}
              onClick={handleCopy}
            />
          </Tooltip>
          <Tooltip title={isMd ? t('code.switchToCode') : t('code.switchToMd')}>
            <Button type="text" size="small" icon={<SwapOutlined style={iconBtnS} />} onClick={handleSwitchType} />
          </Tooltip>
          {!editing && (
            <Tooltip title={t('code.edit')}>
              <Button type="text" size="small" icon={<EditOutlined style={iconBtnS} />} onClick={startEdit} />
            </Tooltip>
          )}
          {canRun && !running && (
            <Tooltip title="Run (Ctrl+Enter)">
              <Button
                type="text" size="small"
                icon={<PlayCircleOutlined style={{ color: C.primary, fontSize: 14 }} />}
                onClick={handleRun}
              />
            </Tooltip>
          )}
          {canRun && running && (
            <Tooltip title={t('code.stop')}>
              <Button
                type="text" size="small"
                icon={<CloseCircleOutlined style={{ color: C.error, fontSize: 14 }} />}
                onClick={handleStop}
              />
            </Tooltip>
          )}
          <Tooltip title={t('topic.delete')}>
            <Button type="text" size="small" icon={<DeleteOutlined style={iconBtnS} />} onClick={() => onDelete(cell.id)} />
          </Tooltip>
          <Tooltip title={t('code.moveUp')}>
            <Button
              type="text" size="small"
              icon={<UpOutlined style={iconBtnS} />}
              disabled={index === 0}
              onClick={() => onMove(cell.id, 'up')}
            />
          </Tooltip>
          <Tooltip title={t('code.moveDown')}>
            <Button
              type="text" size="small"
              icon={<DownOutlined style={iconBtnS} />}
              disabled={index === total - 1}
              onClick={() => onMove(cell.id, 'down')}
            />
          </Tooltip>
          {onInsertAbove && (
            <Tooltip title={t('code.insertAbove')}>
              <Button type="text" size="small" icon={<CaretUpOutlined style={iconBtnS} />} onClick={onInsertAbove} />
            </Tooltip>
          )}
          {onInsertBelow && (
            <Tooltip title={t('code.insertBelow')}>
              <Button type="text" size="small" icon={<CaretDownOutlined style={iconBtnS} />} onClick={onInsertBelow} />
            </Tooltip>
          )}
        </div>
      </div>

      {/* ── Content ── */}
      {editing ? (
        isMd ? (
          <Input.TextArea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            onBlur={saveEdit}
            onKeyDown={(e) => { if (e.key === 'Escape') { setEditing(false); onEditCancel?.(cell.id); } }}
            autoFocus
            style={{ border: 'none', borderRadius: 0, fontSize: 14, resize: 'vertical', minHeight: 80 }}
            autoSize={{ minRows: 3 }}
          />
        ) : isTxt ? (
          <Input.TextArea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            onBlur={saveEdit}
            onKeyDown={(e) => { if (e.key === 'Escape') { setEditing(false); onEditCancel?.(cell.id); } }}
            autoFocus
            style={{ border: 'none', borderRadius: 0, fontSize: 13, resize: 'vertical', minHeight: 80, fontFamily: 'monospace' }}
            autoSize={{ minRows: 3 }}
          />
        ) : (
          <Suspense fallback={
            <div style={{ background: C.codeBg, padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13, fontFamily: 'monospace' }}>
                Loading editor...
              </span>
            </div>
          }>
            <div style={{ height: Math.max(100, (cell.code.split('\n').length + 1) * 20), background: C.codeBg, transition: 'height 0.15s ease' }}>
              <MonacoEditor
                height="100%"
                language={cell.language}
                value={cell.code}
                onChange={(val: any) => { if (val != null) setEditText(val); }}
                onMount={handleEditorMount}
                theme="vs-dark"
                options={{
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  scrollbar: { alwaysConsumeMouseWheel: false },
                  fontSize: 14,
                  lineNumbers: 'on',
                  tabSize: 4,
                  automaticLayout: true,
                  overviewRulerLanes: 0,
                  hideCursorInOverviewRuler: true,
                  renderLineHighlight: 'none',
                }}
              />
            </div>
          </Suspense>
        )
      ) : isMd ? (
        <div style={{ padding: '18px 24px', background: '#fff', cursor: 'text' }} onDoubleClick={startEdit}>
          <MarkdownRenderer content={cell.content} />
        </div>
      ) : isTxt ? (
        <div
          onClick={startEdit}
          style={{ cursor: 'text', padding: '16px 24px', background: '#fff', userSelect: 'none' }}
        >
          <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word', userSelect: 'none', lineHeight: 1.6 }}>
            {cell.code || ' '}
          </pre>
        </div>
      ) : (
        <div
          onClick={startEdit}
          style={{ cursor: 'text', lineHeight: 0, userSelect: 'none' }}
        >
          <SyntaxHighlighter
            language={cell.language}
            style={oneDark}
            customStyle={{ margin: 0, borderRadius: 0, padding: '18px 24px', fontSize: 14, lineHeight: 1.6 }}
            showLineNumbers
            wrapLines
          >
            {cell.code}
          </SyntaxHighlighter>
        </div>
      )}

      {/* ── Output ── */}
      {hasOutput && (
        <div
          style={{
            borderTop: `1px solid ${C.border}`,
            borderLeft: `3px solid ${isError ? C.error : C.success}`,
            background: isError ? 'rgba(239,68,68,0.03)' : 'rgba(16,185,129,0.03)',
            padding: '10px 24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: (output!.stdout || output!.stderr) ? 8 : 0 }}>
            {isError && <CloseCircleOutlined style={{ color: C.error, fontSize: 12 }} />}
            <span style={{ color: C.textSec, fontSize: 11, fontFamily: 'monospace' }}>
              {output!.exit_code === 0 && output!.duration_ms > 0
                ? `Done in ${output!.duration_ms}ms`
                : output!.exit_code !== 0
                  ? `exit: ${output!.exit_code} (${output!.duration_ms}ms)`
                  : ''}
            </span>
          </div>
          {output!.stdout ? (
            <pre style={{ margin: 0, color: C.text, fontFamily: "Consolas, 'Courier New', monospace", fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6 }}>
              {output!.stdout}
            </pre>
          ) : null}
          {output!.stderr ? (
            <pre style={{ margin: '4px 0 0', color: C.error, fontFamily: "Consolas, 'Courier New', monospace", fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6 }}>
              {output!.stderr}
            </pre>
          ) : null}
        </div>
      )}
    </div>
  );
});

export default NotebookCellComp;
