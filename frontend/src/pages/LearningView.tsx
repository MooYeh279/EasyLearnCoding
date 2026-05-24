import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Spin, Button, message, Modal } from 'antd';
import { ArrowLeftOutlined, BookOutlined, CodeOutlined, EditOutlined, DownloadOutlined, RobotOutlined, ReloadOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import type { Topic, Lesson, NotebookCell } from '../types';
import NotebookCellComp from '../components/NotebookCell';
import AiChatSidebar from '../components/AiChatSidebar';
import LangSwitch from '../components/LangSwitch';
import SplitPane from '../components/SplitPane';
import { useContentLang } from '../context/LangContext';
import { parseCells, generateId, cellsToMarkdown, downloadMarkdown } from '../utils/notebook';

/* ── Design tokens ── */
const C = {
  pageBg:        '#faf9f7',
  sidebarBg:     '#fafafc',
  cardBg:        '#ffffff',
  primary:       '#5b5feb',
  primaryBg:     'rgba(91,95,235,0.06)',
  success:       '#10b981',
  warning:       '#f59e0b',
  error:         '#ef4444',
  text:          '#1e1e24',
  textSecondary: '#6b7280',
  textMuted:     '#9ca3af',
  border:        '#e8e8ed',
  borderLight:   '#f0f0f3',
  codeBg:        '#1e1e2e',
  radius:        10,
  radiusSm:      8,
};

export default function LearningView() {
  const { id } = useParams<{ id: string; sectionId: string }>();
  const [searchParams] = useSearchParams();
  const lessonIdParam = searchParams.get('lesson');
  const navigate = useNavigate();
  const { t } = useContentLang();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [currentLesson, setCurrentLesson] = useState<Lesson | null>(null);
  const lessonRef = useRef<Lesson | null>(null);
  const [cells, setCells] = useState<NotebookCell[]>([]);
  const cellsRef = useRef<NotebookCell[]>([]);
  const savingRef = useRef(false);
  const pendingSaveRef = useRef<NotebookCell[] | null>(null);
  const editingRef = useRef(false);
  const [loading, setLoading] = useState(true);
  const [lessonLoading, setLessonLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'dirty' | 'saving'>('saved');

  useEffect(() => {
    if (id) {
      api.getTopic(Number(id))
        .then(setTopic)
        .finally(() => setLoading(false));
    }
  }, [id]);

  useEffect(() => {
    if (!lessonIdParam) return;
    setLessonLoading(true);
    let cancelled = false;
    api.getLesson(Number(lessonIdParam))
      .then((lesson) => {
        if (cancelled) return;
        lessonRef.current = lesson;
        setCurrentLesson(lesson);
        const parsed = parseCells(lesson.content);
        cellsRef.current = parsed;
        setCells(parsed);
        setSaveStatus('saved');
      })
      .catch((err) => {
        if (cancelled) return;
        message.error(t('learn.loadFail') + ': ' + (err?.message || 'Unknown'));
      })
      .finally(() => {
        if (!cancelled) setLessonLoading(false);
      });
    return () => { cancelled = true; };
  }, [lessonIdParam, t]);

  const doSave = useCallback(async (newCells: NotebookCell[], showToast = false): Promise<boolean> => {
    cellsRef.current = newCells;
    setCells(newCells);
    setSaveStatus('saving');

    const lesson = lessonRef.current;
    if (!lesson) return false;

    if (savingRef.current) {
      pendingSaveRef.current = newCells;
      return false;
    }

    savingRef.current = true;
    try {
      await api.updateLesson(lesson.id, JSON.stringify(newCells));
      setSaveStatus('saved');
      if (showToast) message.success(t('learn.saveSuccess'));
      return true;
    } catch (err: any) {
      setSaveStatus('dirty');
      message.error(t('learn.saveFail'));
      return false;
    } finally {
      savingRef.current = false;
      const pending = pendingSaveRef.current;
      if (pending) {
        pendingSaveRef.current = null;
        doSave(pending, false);
      }
    }
  }, [t]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (!currentLesson) return;
        if (editingRef.current && document.activeElement instanceof HTMLElement) {
          document.activeElement.blur();
        }
        doSave(cellsRef.current, true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [currentLesson, doSave]);

  const handleCellChange = useCallback((cellId: string, updates: Partial<NotebookCell>) => {
    const current = cellsRef.current;
    const updated = current.map((c) => c.id === cellId ? { ...c, ...updates } as NotebookCell : c);
    editingRef.current = false;
    doSave(updated);
  }, [doSave]);

  const handleEditStart = useCallback((_cellId: string) => {
    setSaveStatus('dirty');
    editingRef.current = true;
  }, []);

  const handleEditCancel = useCallback((_cellId: string) => {
    setSaveStatus('saved');
    editingRef.current = false;
  }, []);

  const handleCellDelete = useCallback((cellId: string) => {
    doSave(cellsRef.current.filter((c) => c.id !== cellId));
  }, [doSave]);

  const handleCellMove = useCallback((cellId: string, direction: 'up' | 'down') => {
    const current = cellsRef.current;
    const idx = current.findIndex((c) => c.id === cellId);
    if (idx === -1) return;
    const newIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (newIdx < 0 || newIdx >= current.length) return;
    const updated = [...current];
    [updated[idx], updated[newIdx]] = [updated[newIdx], updated[idx]];
    doSave(updated);
  }, [doSave]);

  const addCell = useCallback((type: 'markdown' | 'code') => {
    const newCell: NotebookCell = type === 'markdown'
      ? { id: generateId(), type: 'markdown', content: '## New Section\n\nWrite here...' }
      : { id: generateId(), type: 'code', language: 'python', code: '# write code here', output: null };
    doSave([...cellsRef.current, newCell]);
  }, [doSave]);

  const handleRegenerate = useCallback(() => {
    const lesson = lessonRef.current;
    if (!lesson) return;
    Modal.confirm({
      title: t('learn.regenerateConfirm'),
      okText: t('learn.regenerate'),
      cancelText: t('course.cancel'),
      okButtonProps: { style: { background: C.primary, borderColor: C.primary } },
      onOk: async () => {
        setRegenerating(true);
        try {
          const updated = await api.regenerateLesson(lesson.id);
          lessonRef.current = { ...lesson, content: updated.content };
          setCurrentLesson({ ...lesson, content: updated.content });
          const parsed = parseCells(updated.content);
          cellsRef.current = parsed;
          setCells(parsed);
          setSaveStatus('saved');
          message.success(t('learn.regenerateSuccess'));
        } catch (err: any) {
          message.error(t('learn.regenerateFail'));
        } finally {
          setRegenerating(false);
        }
      },
    });
  }, [t]);

  // ── derived data ──
  const sections = topic?.sections || [];

  // ── shared button styles ──
  const btnGhost: React.CSSProperties = {
    borderRadius: C.radiusSm,
    borderColor: C.border,
    color: C.textSecondary,
    fontWeight: 400,
  };

  // ── Content area (shared between chat-open and chat-closed layouts) ──
  const contentBody = (
    <div style={{ height: '100%', overflow: 'auto', background: C.pageBg }}>
      {lessonLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
          <Spin size="large">
            <span style={{ color: C.textSecondary, fontSize: 13 }}>{t('learn.loading')}</span>
          </Spin>
        </div>
      ) : currentLesson ? (
        <div style={{ maxWidth: 820, margin: '0 auto', padding: '40px 32px' }}>

          {/* ── Lesson header ── */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 600,
                  color: C.text,
                  letterSpacing: '-0.02em',
                  lineHeight: 1.3,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {currentLesson.title}
              </div>
              {saveStatus === 'saved' ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: C.textMuted, fontSize: 12, flexShrink: 0 }}>
                  <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: C.success }} />
                  Saved
                </span>
              ) : saveStatus === 'saving' ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: C.warning, fontSize: 12, flexShrink: 0 }}>
                  <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: C.warning, animation: 'statusPulse 1.2s ease-in-out infinite' }} />
                  Saving...
                </span>
              ) : saveStatus === 'dirty' ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: C.textSecondary, fontSize: 12, flexShrink: 0 }}>
                  <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: C.textMuted }} />
                  Unsaved
                </span>
              ) : null}
            </div>

            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              <Button size="small" icon={<ReloadOutlined />} loading={regenerating} onClick={handleRegenerate} style={btnGhost}>
                {regenerating ? t('learn.regenerating') : t('learn.regenerate')}
              </Button>
              <Button size="small" icon={<DownloadOutlined />} onClick={() => downloadMarkdown(currentLesson.title, cellsToMarkdown(cells))} style={btnGhost}>
                {t('learn.exportMd')}
              </Button>
              <Button
                size="small"
                icon={<RobotOutlined />}
                onClick={() => setChatOpen(!chatOpen)}
                style={{ ...btnGhost, ...(chatOpen ? { background: C.primary, color: '#fff', borderColor: C.primary } : {}) }}
              >
                {t('chat.title')}
              </Button>
            </div>
          </div>

          {/* ── Cells ── */}
          {cells.map((cell, idx) => (
            <NotebookCellComp
              key={cell.id}
              cell={cell}
              index={idx}
              total={cells.length}
              onChange={handleCellChange}
              onDelete={handleCellDelete}
              onMove={handleCellMove}
              onEditStart={handleEditStart}
              onEditCancel={handleEditCancel}
            />
          ))}

          {/* ── Empty state ── */}
          {cells.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 40px', background: C.cardBg, borderRadius: C.radius, border: `1px dashed ${C.border}` }}>
              <BookOutlined style={{ fontSize: 40, color: '#d4d4dc', marginBottom: 16 }} />
              <div style={{ color: C.textSecondary, fontSize: 14, marginBottom: 16 }}>{t('learn.placeholder')}</div>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
                <Button icon={<EditOutlined />} onClick={() => addCell('markdown')} style={{ borderRadius: C.radiusSm }}>+ Markdown</Button>
                <Button icon={<CodeOutlined />} onClick={() => addCell('code')} style={{ borderRadius: C.radiusSm }}>+ Code</Button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 20 }}>
              <Button size="small" icon={<EditOutlined />} onClick={() => addCell('markdown')} style={{ borderRadius: C.radiusSm, color: C.textSecondary, borderColor: C.borderLight }}>+ Markdown</Button>
              <Button size="small" icon={<CodeOutlined />} onClick={() => addCell('code')} style={{ borderRadius: C.radiusSm, color: C.textSecondary, borderColor: C.borderLight }}>+ Code</Button>
            </div>
          )}
        </div>
      ) : (
        <div style={{ textAlign: 'center', marginTop: 120 }}>
          <BookOutlined style={{ fontSize: 56, color: '#d4d4dc', marginBottom: 20 }} />
          <div style={{ color: C.textSecondary, fontSize: 15 }}>{t('learn.placeholder')}</div>
        </div>
      )}
    </div>
  );

  return (
    <div style={{ height: '100vh' }}>

      {/* ================================================================
          LEFT SIDEBAR + RIGHT AREA — resizable split
          ================================================================ */}
      <SplitPane initialLeft="260px" minLeft="200px" minRight="300px" style={{ height: '100%' }}>
        {/* Left sidebar */}
        <div style={{
          height: '100%', display: 'flex', flexDirection: 'column',
          background: C.sidebarBg, overflow: 'auto',
        }}>
          {/* Sidebar header */}
          <div style={{ padding: '20px 16px 14px', borderBottom: `1px solid ${C.borderLight}` }}>
            <a
              onClick={() => navigate(`/topics/${id}`)}
              style={{
                cursor: 'pointer', fontSize: 13, color: C.textSecondary,
                display: 'inline-flex', alignItems: 'center', gap: 6,
                textDecoration: 'none', transition: 'color 0.15s',
              }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.color = C.primary; }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.color = C.textSecondary; }}
            >
              <ArrowLeftOutlined style={{ fontSize: 12 }} />
              {t('learn.back')}
            </a>

            {topic && (
              <div style={{ fontSize: 15, fontWeight: 500, color: C.text, marginTop: 14, lineHeight: 1.4, wordBreak: 'break-word' }}>
                {topic.title}
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <LangSwitch />
            </div>
          </div>

          {/* Lesson menu */}
          {loading ? (
            <Spin style={{ display: 'block', margin: '40px auto' }} />
          ) : (
            <div style={{ padding: '12px 0' }}>
              {sections.map((sec) => (
                <div key={sec.title} style={{ marginBottom: 4 }}>
                  <div style={{ padding: '6px 16px 2px', fontSize: 11, fontWeight: 600, color: C.textSecondary, letterSpacing: '0.3px' }}>
                    {sec.title}
                  </div>
                  {(sec.lessons || []).map((les) => {
                    const isActive = currentLesson?.id === les.id;
                    return (
                      <div
                        key={les.id}
                        onClick={() => navigate(`/topics/${id}/sections/${sec.id}?lesson=${les.id}`)}
                        style={{
                          padding: '7px 16px 7px 12px', margin: '1px 8px',
                          borderRadius: C.radiusSm, cursor: 'pointer',
                          fontSize: 13, lineHeight: 1.4,
                          color: isActive ? C.primary : C.text,
                          background: isActive ? C.primaryBg : 'transparent',
                          borderLeft: isActive ? `3px solid ${C.primary}` : '3px solid transparent',
                          transition: 'all 0.15s',
                        }}
                        onMouseEnter={(e) => { if (!isActive) (e.target as HTMLElement).style.background = '#f0f0f5'; }}
                        onMouseLeave={(e) => { if (!isActive) (e.target as HTMLElement).style.background = 'transparent'; }}
                      >
                        {les.title}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: content, or content + chat (resizable) */}
        {chatOpen && currentLesson ? (
          <SplitPane initialLeft="58%" minLeft="350px" minRight="280px" style={{ height: '100%' }}>
            {contentBody}
            <div style={{ height: '100%', background: C.cardBg, borderLeft: `1px solid ${C.border}`, overflow: 'hidden' }}>
              <AiChatSidebar
                lessonId={currentLesson.id}
                lessonTitle={currentLesson.title}
                onCollapse={() => setChatOpen(false)}
              />
            </div>
          </SplitPane>
        ) : (
          contentBody
        )}
      </SplitPane>
    </div>
  );
}
