import { useState, useCallback, useEffect, lazy, Suspense } from 'react';
import { Button, Spin, Tooltip } from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { useContentLang } from '../context/LangContext';
import type { ExerciseRunResponse } from '../types';

const MonacoEditor = lazy(() => import('@monaco-editor/react').then(m => ({ default: m.Editor })));

const CODE_STORE_PREFIX = 'exercise_code_';

function loadCode(exerciseId: number | undefined, template: string): string {
  if (!exerciseId) return template;
  try {
    const saved = localStorage.getItem(CODE_STORE_PREFIX + exerciseId);
    return saved ?? template;
  } catch { return template; }
}

function saveCode(exerciseId: number | undefined, code: string) {
  if (!exerciseId) return;
  try { localStorage.setItem(CODE_STORE_PREFIX + exerciseId, code); } catch { /* quota exceeded */ }
}

interface Props {
  exerciseId?: number;
  template: string;
  running: boolean;
  testResult: ExerciseRunResponse | null;
  onRun: (code: string) => void;
}

const C = {
  primary: '#5b5feb',
  success: '#10b981',
  successBg: '#ecfdf5',
  error: '#ef4444',
  errorBg: '#fef2f2',
  text: '#1e1e24',
  textSec: '#6b7280',
  textMuted: '#9ca3af',
  border: '#e8e8ed',
  borderLight: '#f0f0f3',
  codeBg: '#282c34',
  radiusSm: 8,
};

export default function TestRunner({ exerciseId, template, running, testResult, onRun }: Props) {
  const { t } = useContentLang();
  const [code, setCode] = useState(() => loadCode(exerciseId, template));

  // Persist code changes to localStorage (debounced by React batching)
  useEffect(() => {
    saveCode(exerciseId, code);
  }, [code, exerciseId]);

  // Reload code when exercise changes
  useEffect(() => {
    setCode(loadCode(exerciseId, template));
  }, [exerciseId, template]);

  const handleEditorMount = useCallback((editor: any, monaco: any) => {
    editor.addAction({
      id: 'run-tests',
      label: 'Run Tests',
      keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
      run: () => onRun(editor.getValue()),
    });
  }, [onRun]);

  const handleReset = () => setCode(template);

  const hasResults = testResult && (testResult.results.length > 0 || testResult.error);

  const passedCount = testResult?.results?.filter(r => r.passed).length ?? 0;
  const totalCount = testResult?.results?.length ?? 0;

  return (
    <>
      {/* Editor header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 16px', background: C.codeBg, borderBottom: '1px solid #3a3f4b',
      }}>
        <span style={{ color: '#abb2bf', fontSize: 12, fontFamily: 'monospace' }}>solution</span>
        <Tooltip title={t('exercise.resetCode')}>
          <Button
            size="small" type="text"
            icon={<ReloadOutlined style={{ color: '#abb2bf', fontSize: 12 }} />}
            onClick={handleReset}
            style={{ border: '1px solid #4a4f5b', borderRadius: 4 }}
          />
        </Tooltip>
      </div>

      {/* Monaco editor — minHeight:0 + overflow:hidden lets it shrink when results appear */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', background: C.codeBg }}>
        <Suspense fallback={
          <div style={{ background: C.codeBg, padding: '20px 24px' }}>
            <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>{t('exercise.editorLoading')}</span>
          </div>
        }>
          <MonacoEditor
            height="100%"
            language="python"
            value={code}
            onChange={(val: any) => { if (val != null) setCode(val); }}
            onMount={handleEditorMount}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              fontSize: 14,
              lineNumbers: 'on',
              tabSize: 4,
              automaticLayout: true,
              overviewRulerLanes: 0,
              hideCursorInOverviewRuler: true,
              renderLineHighlight: 'none',
            }}
          />
        </Suspense>
      </div>

      {/* Run button bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 16px', borderTop: `1px solid ${C.border}`, borderBottom: `1px solid ${C.borderLight}`,
        background: '#fafbfc',
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Button
            type="primary"
            icon={running ? <Spin size="small" /> : <PlayCircleOutlined />}
            onClick={() => onRun(code)}
            loading={running}
            style={{
              borderRadius: C.radiusSm,
              background: C.primary,
              borderColor: C.primary,
              fontWeight: 500,
            }}
          >
            {running ? t('exercise.running') : t('exercise.runTests')}
          </Button>
        </div>
        <span style={{ fontSize: 12, color: C.textMuted }}>Ctrl+Enter</span>
      </div>

      {/* Test results panel — capped at 45% of viewport so it's always visible */}
      {hasResults && (
        <div style={{
          borderTop: `1px solid ${C.border}`, background: '#fff',
          maxHeight: '45vh', overflowY: 'auto', flexShrink: 0,
        }}>
          {/* Results header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 16px', borderBottom: `1px solid ${C.borderLight}`,
            background: '#fafbfc',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{t('exercise.testResults')}</span>
              {totalCount > 0 && (
                <span style={{ fontSize: 12, color: C.textMuted }}>
                  {t('exercise.testCases', { n: totalCount })}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
              {passedCount > 0 && (
                <span style={{ color: C.success, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: C.success, display: 'inline-block' }} />
                  {t('exercise.passed', { n: passedCount })}
                </span>
              )}
              {totalCount - passedCount > 0 && (
                <span style={{ color: C.error, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: C.error, display: 'inline-block' }} />
                  {t('exercise.failed', { n: totalCount - passedCount })}
                </span>
              )}
              {testResult!.all_passed && totalCount > 0 && (
                <span style={{ color: C.success, fontWeight: 500, fontSize: 13 }}>
                  {t('exercise.allPassed')}
                </span>
              )}
            </div>
          </div>

          {/* Top-level error (e.g. syntax error, no results found) */}
          {testResult!.error && (
            <div style={{ padding: '10px 16px' }}>
              <div style={{
                padding: '10px 14px',
                background: C.errorBg, borderLeft: `3px solid ${C.error}`,
                borderRadius: `0 ${C.radiusSm}px ${C.radiusSm}px 0`,
                fontFamily: 'monospace', fontSize: 12, color: C.textSec,
                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              }}>
                {testResult!.error}
              </div>
            </div>
          )}

          {/* Raw output for debugging */}
          {testResult!.raw_output && (
            <div style={{ padding: '0 16px 10px' }}>
              <details style={{ fontSize: 12 }}>
                <summary style={{ color: C.textMuted, cursor: 'pointer' }}>raw output</summary>
                <pre style={{
                  marginTop: 6, padding: '8px 10px',
                  background: '#f5f5f5', borderRadius: C.radiusSm,
                  fontFamily: 'monospace', fontSize: 11, color: C.textSec,
                  whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 120, overflowY: 'auto',
                }}>{testResult!.raw_output}</pre>
              </details>
            </div>
          )}

          {/* Individual test cases */}
          {testResult!.results.map((r, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '4px 16px' }}>
              <span style={{
                width: 18, height: 18, borderRadius: '50%',
                background: r.passed ? C.success : C.error,
                color: '#fff', fontSize: 10, fontWeight: 700,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, marginTop: 2,
              }}>
                {r.passed ? '✓' : '✗'}
              </span>
              <div style={{ flex: 1 }}>
                <span style={{ color: C.text, fontWeight: 500 }}>{r.name}</span>
                {!r.passed && r.error && (
                  <div style={{
                    marginTop: 6, padding: '8px 12px',
                    background: C.errorBg, borderLeft: `3px solid ${C.error}`,
                    borderRadius: `0 ${C.radiusSm}px ${C.radiusSm}px 0`,
                    fontFamily: 'monospace', fontSize: 12, color: C.textSec,
                    whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                  }}>
                    {r.error}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
