import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Input, Typography, Tag, Spin, Alert, message, Progress, Space, Popconfirm } from 'antd';
import {
  ThunderboltOutlined, CheckCircleOutlined,
  SendOutlined, ReloadOutlined, CloseOutlined, CheckOutlined,
  PlusOutlined, DeleteOutlined, HolderOutlined, ExperimentOutlined,
} from '@ant-design/icons';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import { langPlaceholder } from '../i18n/translations';
import StatusProgress from '../components/StatusProgress';
import type { Topic, TopicOutline, OutlineSection, Exercise } from '../types';
import AppLayout from '../components/AppLayout';

const { Text } = Typography;

// -- Design System -----------------------------------------------------------
const DS = {
  pageBg: '#faf9f7',
  cardBg: '#ffffff',
  primary: '#5b5feb',
  primaryLight: '#eef0ff',
  primaryGlow: '0 0 0 4px rgba(91, 95, 235, 0.12)',
  success: '#10b981',
  successBg: '#ecfdf5',
  warning: '#f59e0b',
  warningBg: '#fffbeb',
  error: '#ef4444',
  errorBg: '#fef2f2',
  text: '#1e1e24',
  textSecondary: '#6b7280',
  textMuted: '#9ca3af',
  border: '#e8e8ed',
  borderLight: '#f0f0f3',
  radius: 14,
  radiusSm: 10,
  radiusXs: 8,
};

const statusStep: Record<string, number> = {
  draft: 0,
  generating_outline: 0,
  outline_ready: 1,
  generating_content: 1,
  content_ready: 2,
};

// -- Shared card style -------------------------------------------------------
const cardStyle: React.CSSProperties = {
  background: DS.cardBg,
  borderRadius: DS.radius,
  border: `1px solid ${DS.border}`,
  marginBottom: 20,
  padding: 28,
};

const cardTitleStyle: React.CSSProperties = {
  fontSize: 17,
  fontWeight: 600,
  color: DS.text,
  marginBottom: 20,
  letterSpacing: '-0.01em',
};

// -- Status icon helper ------------------------------------------------------
function LessonStatusIcon({ status, failed }: { status: string; failed?: boolean }) {
  if (status === 'generated') {
    if (failed) {
      return <CloseOutlined style={{ color: DS.error, fontSize: 14 }} />;
    }
    return <CheckCircleOutlined style={{ color: DS.success, fontSize: 14 }} />;
  }
  if (status === 'generating') {
    return (
      <Spin size="small">
        <span style={{ width: 14, height: 14, display: 'inline-block' }} />
      </Spin>
    );
  }
  // pending
  return (
    <span style={{
      width: 14, height: 14, borderRadius: '50%',
      border: `2px solid ${DS.textMuted}`,
      display: 'inline-block',
    }} />
  );
}

export default function TopicDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { contentLang, t } = useContentLang();
  const [topic, setTopic] = useState<Topic | null>(null);
  const [outline, setOutline] = useState<TopicOutline | null>(null);
  const [feedback, setFeedback] = useState('');
  const [pageLoading, setPageLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [retryingLessons, setRetryingLessons] = useState<Set<number>>(new Set());
  const [editingSectionIdx, setEditingSectionIdx] = useState<number | null>(null);
  const [editSectionTitle, setEditSectionTitle] = useState('');
  const [editingLessonKey, setEditingLessonKey] = useState<string | null>(null);
  const [editLessonTitle, setEditLessonTitle] = useState('');
  const [dragSecIdx, setDragSecIdx] = useState<number | null>(null);
  const [dragLesKey, setDragLesKey] = useState<string | null>(null);
  const [generatingExercise, setGeneratingExercise] = useState<number | null>(null);
  const [sectionExercises, setSectionExercises] = useState<Record<number, Exercise[]>>({});
  const [topicExercise, setTopicExercise] = useState<Exercise | null>(null);
  const [generatingTopicExercise, setGeneratingTopicExercise] = useState(false);

  // -- Drag and drop handlers --

  const onSectionDragStart = (idx: number) => setDragSecIdx(idx);

  const onSectionDragOver = (e: React.DragEvent) => e.preventDefault();

  const onSectionDrop = (targetIdx: number) => {
    if (dragSecIdx === null || !outline || dragSecIdx === targetIdx) { setDragSecIdx(null); return; }
    const updated = [...outline.sections];
    const [moved] = updated.splice(dragSecIdx, 1);
    updated.splice(targetIdx, 0, moved);
    setDragSecIdx(null);
    setOutline({ ...outline, sections: updated });
    persistOutline(updated);
  };

  const onLessonDragStart = (secIdx: number, lesIdx: number) => setDragLesKey(`${secIdx}:${lesIdx}`);

  const onLessonDragOver = (e: React.DragEvent) => e.preventDefault();

  const onLessonDrop = (targetSecIdx: number, targetLesIdx: number) => {
    if (!dragLesKey || !outline) return;
    const [srcSecStr, srcLesStr] = dragLesKey.split(':');
    const srcSecIdx = Number(srcSecStr);
    const srcLesIdx = Number(srcLesStr);
    if (srcSecIdx === targetSecIdx && srcLesIdx === targetLesIdx) { setDragLesKey(null); return; }
    const updated = outline.sections.map((s) => ({ ...s, lessons: [...s.lessons] }));
    const [moved] = updated[srcSecIdx].lessons.splice(srcLesIdx, 1);
    updated[targetSecIdx].lessons.splice(targetLesIdx, 0, moved);
    setDragLesKey(null);
    setOutline({ ...outline, sections: updated });
    persistOutline(updated);
  };

  const isGenerating = generating || topic?.status === 'generating_outline' || topic?.status === 'generating_content';
  const genStatus = topic?.status === 'generating_outline'
    ? t('topic.genOutlineStatus')
    : topic?.status === 'generating_content'
      ? t('topic.genContentStatus')
      : '';
  const genProgress = (() => {
    const gp = topic?.generation_progress;
    if (gp) {
      return { current: gp.current, total: gp.total, lesson: gp.current_lesson || '' };
    }
    if (topic?.sections && outline?.sections) {
      const current = topic.sections.reduce((sum, s) => sum + (s.lessons || []).filter(l => l.content?.length > 0).length, 0);
      const total = outline.sections.reduce((sum, s) => sum + s.lessons.length, 0);
      return { current, total, lesson: '' };
    }
    return { current: 0, total: 0, lesson: '' };
  })();

  const getLessonStatus = (sectionTitle: string, lessonTitle: string): { status: 'pending' | 'generating' | 'generated'; lessonId?: number; sectionId?: number; failed?: boolean } => {
    if (topic?.sections) {
      for (const sec of topic.sections) {
        if (sec.title === sectionTitle) {
          for (const les of (sec.lessons || [])) {
            if (les.title === lessonTitle) {
              const isEmptyOrError = !les.content
                || les.content === '[]'
                || les.content.includes('Generation failed');
              const hasContent = !isEmptyOrError;
              const failedIds: number[] = (topic.generation_progress as any)?.failed_lesson_ids || [];
              const failed = failedIds.includes(les.id) || (!hasContent && !!les.content);
              if (hasContent || failed) {
                return { status: 'generated', lessonId: les.id, sectionId: sec.id, failed };
              }
              break;
            }
          }
        }
      }
    }
    const gp = topic?.generation_progress;
    if (gp && gp.current_section === sectionTitle && gp.current_lesson === lessonTitle) {
      return { status: 'generating' };
    }
    return { status: 'pending' };
  };

  // Count lessons in the outline that still need content generation
  const pendingLessonCount = (() => {
    if (!outline?.sections) return 0;
    let count = 0;
    for (const sec of outline.sections) {
      for (const les of sec.lessons) {
        const ls = getLessonStatus(sec.title, les.title);
        if (ls.status === 'pending' || ls.failed) count++;
      }
    }
    return count;
  })();

  // Distinguish failed lessons (were attempted, need retry) from new lessons (never attempted)
  const failedRetryCount = (() => {
    if (!outline?.sections) return 0;
    let count = 0;
    for (const sec of outline.sections) {
      for (const les of sec.lessons) {
        const ls = getLessonStatus(sec.title, les.title);
        if (ls.failed) count++;
      }
    }
    return count;
  })();


  useEffect(() => {
    if (id) {
      Promise.all([
        api.getTopic(Number(id)),
        api.getOutline(Number(id)).catch(() => null),
      ]).then(([t, o]) => {
        setTopic(t);
        setOutline(o);
      }).catch(() => message.error(t('topic.loadFail')))
        .finally(() => setPageLoading(false));
    }
  }, [id, t]);

  // Poll for progress when topic is generating
  useEffect(() => {
    const isGenStatus = topic?.status === 'generating_outline' || topic?.status === 'generating_content';
    if (!id || !isGenStatus) return;
    const timer = setInterval(async () => {
      try {
        const updated = await api.getTopic(Number(id));
        setTopic((prev) => {
          if (!prev) return updated;
          const prevGp = prev.generation_progress;
          const newGp = updated.generation_progress;
          if (prevGp && newGp) {
            const prevCurrent = prevGp.current || 0;
            const newCurrent = newGp.current || 0;
            if (prevCurrent > newCurrent) {
              return { ...updated, generation_progress: prevGp };
            }
            if (prevCurrent === newCurrent && prevGp.current_section) {
              return { ...updated, generation_progress: prevGp };
            }
          } else if (prevGp && !newGp) {
            return { ...updated, generation_progress: prevGp };
          }
          return updated;
        });
        if (updated.status !== 'generating_outline' && updated.status !== 'generating_content') {
          clearInterval(timer);
          if (updated.status === 'outline_ready' || updated.status === 'content_ready') {
            api.getOutline(Number(id)).then(o => setOutline(o)).catch(() => {});
          }
        }
      } catch { /* ignore */ }
    }, 2000);
    return () => clearInterval(timer);
  }, [topic?.status, id]);

  // Load existing exercises for sections and topic
  useEffect(() => {
    if (!topic || !id) return;
    const secs = topic.sections || [];
    Promise.all([
      ...secs.map((sec) =>
        api.getSectionExercises(sec.id).catch(() => [] as Exercise[])
      ),
      api.getTopicExercises(Number(id)).catch(() => [] as Exercise[]),
    ]).then((results) => {
      const secResults = results.slice(0, secs.length);
      const topicResults = results[secs.length] as Exercise[];
      const map: Record<number, Exercise[]> = {};
      secs.forEach((sec, i) => { map[sec.id] = secResults[i] || []; });
      setSectionExercises(map);
      // Pick the first topic-level exercise
      const topicEx = topicResults.find(e => e.type === 'topic');
      if (topicEx) setTopicExercise(topicEx);
    }).catch(() => {});
  }, [topic, id]);

  const handleGenerateExercise = async (sectionId: number) => {
    setGeneratingExercise(sectionId);
    try {
      const exercise = await api.generateSectionExercise(sectionId);
      setSectionExercises((prev) => ({
        ...prev,
        [sectionId]: [...(prev[sectionId] || []), exercise],
      }));
      message.success(t('exercise.generateSuccess'));
    } catch (err: any) {
      message.error(t('exercise.generateFail'));
    } finally {
      setGeneratingExercise(null);
    }
  };

  const handleGenerateTopicExercise = async () => {
    if (!id) return;
    setGeneratingTopicExercise(true);
    try {
      const exercise = await api.generateTopicExercise(Number(id));
      setTopicExercise(exercise);
      message.success(t('exercise.generateSuccess'));
    } catch (err: any) {
      message.error(t('exercise.generateFail'));
    } finally {
      setGeneratingTopicExercise(false);
    }
  };

  // -- Persist helpers (auto-save outline changes to backend) --

  const persistOutline = async (sections: OutlineSection[]) => {
    if (!id) return;
    try {
      await api.updateOutline(Number(id), sections);
    } catch {
      message.error(t('topic.aiFail'));
    }
  };

  const handleGenerateOutline = async (withFeedback?: string) => {
    if (!id || !topic) return;
    setGenerating(true);
    try {
      const result = await api.generateOutline(Number(id), topic.title, withFeedback, contentLang);
      setOutline(result);
      const updatedTopic = await api.getTopic(Number(id));
      setTopic(updatedTopic);
      message.success(withFeedback ? t('topic.outlineRegenOk') : t('topic.outlineGenOk'));
    } catch {
      message.error(t('topic.aiFail'));
    } finally {
      setGenerating(false);
    }
  };

  const handleSendFeedback = async () => {
    if (!feedback.trim()) return;
    const fb = feedback.trim();
    setFeedback('');
    await handleGenerateOutline(fb);
  };

  const handleGenerateContent = async () => {
    if (!id || !topic) return;
    setGenerating(true);
    try {
      const result = await api.generateContentStream(Number(id), contentLang);
      if (result.status === 'already_generating') {
        message.info(t('topic.alreadyGenerating'));
      } else {
        message.success(t('topic.contentGenStarted'));
        const updatedTopic = await api.getTopic(Number(id));
        setTopic(updatedTopic);
      }
    } catch (err: any) {
      message.error(err?.message || t('topic.contentGenFail'));
    } finally {
      setGenerating(false);
    }
  };

  const handleRetryLesson = async (lessonId: number) => {
    setRetryingLessons((prev) => new Set(prev).add(lessonId));
    try {
      await api.regenerateLesson(lessonId);
      message.success(t('topic.contentGenOk'));
      const updatedTopic = await api.getTopic(Number(id!));
      setTopic(updatedTopic);
    } catch {
      message.error(t('topic.contentGenFail'));
    } finally {
      setRetryingLessons((prev) => {
        const next = new Set(prev);
        next.delete(lessonId);
        return next;
      });
    }
  };

  // -- Section editing --

  const startEditSection = (idx: number, title: string) => {
    setEditingSectionIdx(idx);
    setEditSectionTitle(title);
    setEditingLessonKey(null);
  };

  const saveEditSection = () => {
    if (editingSectionIdx === null || !outline) return;
    const updated = outline.sections.map((s, i) =>
      i === editingSectionIdx ? { ...s, title: editSectionTitle } : s
    );
    setOutline({ ...outline, sections: updated });
    setEditingSectionIdx(null);
    persistOutline(updated);
  };

  const deleteSection = (idx: number) => {
    if (!outline) return;
    const updated = outline.sections.filter((_, i) => i !== idx);
    setOutline({ ...outline, sections: updated });
    persistOutline(updated);
  };

  const addSection = () => {
    if (!outline) return;
    const updated = [...outline.sections, { title: t('topic.newSection'), description: '', lessons: [] }];
    setOutline({ ...outline, sections: updated });
    persistOutline(updated);
  };

  // -- Lesson editing --

  const startEditLesson = (secIdx: number, lesIdx: number, title: string) => {
    setEditingLessonKey(`${secIdx}:${lesIdx}`);
    setEditLessonTitle(title);
    setEditingSectionIdx(null);
  };

  const saveEditLesson = () => {
    if (!editingLessonKey || !outline) return;
    const [secIdx, lesIdx] = editingLessonKey.split(':').map(Number);
    const updated = outline.sections.map((s, i) => {
      if (i !== secIdx) return s;
      return {
        ...s,
        lessons: s.lessons.map((l, j) => j === lesIdx ? { ...l, title: editLessonTitle } : l),
      };
    });
    setOutline({ ...outline, sections: updated });
    setEditingLessonKey(null);
    persistOutline(updated);
  };

  const addLesson = (secIdx: number) => {
    if (!outline) return;
    const updated = outline.sections.map((s, i) => {
      if (i !== secIdx) return s;
      return { ...s, lessons: [...s.lessons, { title: t('topic.newLesson') }] };
    });
    setOutline({ ...outline, sections: updated });
    persistOutline(updated);
  };

  const deleteLesson = (secIdx: number, lesIdx: number) => {
    if (!outline) return;
    const updated = outline.sections.map((s, i) => {
      if (i !== secIdx) return s;
      return { ...s, lessons: s.lessons.filter((_, j) => j !== lesIdx) };
    });
    setOutline({ ...outline, sections: updated });
    persistOutline(updated);
  };

  if (pageLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />;
  }
  if (!topic) return <Alert type="error" message={t('topic.notFound')} style={{ margin: 40 }} />;

  const currentStep = statusStep[topic.status] || 0;

  return (
    <AppLayout breadcrumb={[{ title: t('app.title'), path: '/' }, { title: topic.title }]}>
      {/* ---- Status Progress Card ---- */}
      <div style={cardStyle}>
        <StatusProgress
          steps={[
            { title: t('topic.step1Title'), description: t('topic.step1Desc') },
            { title: t('topic.step2Title'), description: t('topic.step2Desc') },
            { title: t('topic.step3Title'), description: t('topic.step3Desc') },
          ]}
          current={currentStep}
          loading={isGenerating}
        />
        {topic.status === 'content_ready' && (
          <div style={{ textAlign: 'center', marginTop: 8, display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Button
              type="primary"
              onClick={() => {
                if (outline?.sections?.[0]) {
                  const sec = outline.sections[0];
                  const les = sec.lessons?.[0];
                  if (les) {
                    const dbSec = topic.sections?.find(s => s.title === sec.title);
                    const dbLes = dbSec?.lessons?.find(l => l.title === les.title);
                    if (dbSec && dbLes) {
                      navigate(`/topics/${id}/sections/${dbSec.id}?lesson=${dbLes.id}`);
                    }
                  }
                }
              }}
              style={{
                height: 48,
                padding: '0 48px',
                fontSize: 16,
                fontWeight: 600,
                borderRadius: DS.radiusSm,
                background: `linear-gradient(135deg, ${DS.primary} 0%, #7c3aed 100%)`,
                border: 'none',
                boxShadow: `0 4px 16px rgba(91, 95, 235, 0.3), ${DS.primaryGlow}`,
                maxWidth: 300,
                width: '100%',
              }}
              icon={<ThunderboltOutlined />}
            >
              {t('topic.startLearning')}
            </Button>
            {topicExercise ? (
              <Button
                onClick={() => navigate(`/topics/${id}/exercise/${topicExercise.id}`)}
                style={{
                  height: 48,
                  padding: '0 36px',
                  fontSize: 16,
                  fontWeight: 600,
                  borderRadius: DS.radiusSm,
                  borderColor: DS.primary,
                  color: DS.primary,
                  maxWidth: 300,
                  width: '100%',
                }}
                icon={<ExperimentOutlined />}
              >
                {t('exercise.startBtn')}
              </Button>
            ) : (
              <Button
                onClick={handleGenerateTopicExercise}
                loading={generatingTopicExercise}
                style={{
                  height: 48,
                  padding: '0 36px',
                  fontSize: 16,
                  fontWeight: 600,
                  borderRadius: DS.radiusSm,
                  borderColor: DS.primary,
                  color: DS.primary,
                  maxWidth: 300,
                  width: '100%',
                }}
                icon={<ExperimentOutlined />}
              >
                {generatingTopicExercise ? t('exercise.generating') : t('exercise.comprehensiveBtn')}
              </Button>
            )}
          </div>
        )}
      </div>

      {/* ---- Generation Progress Card ---- */}
      {isGenerating && (
        <div style={{
          ...cardStyle,
          borderLeft: `4px solid ${DS.primary}`,
        }}>
          {genProgress.total > 0 ? (
            <div>
              <Progress
                percent={Math.round((genProgress.current / genProgress.total) * 100)}
                strokeColor={DS.primary}
                trailColor={DS.borderLight}
                strokeWidth={6}
              />
              <Text style={{ color: DS.textSecondary, fontSize: 13 }}>
                {t('topic.genProgress', { current: genProgress.current, total: genProgress.total, lesson: genProgress.lesson })}
              </Text>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Spin size="small" />
              <Text style={{ color: DS.textSecondary, fontSize: 13 }}>{genStatus}</Text>
            </div>
          )}
        </div>
      )}

      {/* ---- Generate Outline Card (draft) ---- */}
      {topic.status === 'draft' && (
        <div style={{ ...cardStyle, textAlign: 'center' }}>
          <Text style={{ color: DS.textSecondary, fontSize: 14, display: 'block', marginBottom: 16 }}>
            {t('topic.genOutlineHint')}
          </Text>
          <Button
            type="primary"
            size="large"
            onClick={() => handleGenerateOutline()}
            loading={isGenerating}
            icon={<ThunderboltOutlined />}
            style={{
              height: 48,
              padding: '0 40px',
              fontSize: 16,
              fontWeight: 600,
              borderRadius: DS.radiusSm,
              background: `linear-gradient(135deg, ${DS.primary} 0%, #7c3aed 100%)`,
              border: 'none',
              boxShadow: `0 4px 16px rgba(91, 95, 235, 0.3)`,
            }}
          >
            {t('topic.genOutlineBtn')}
          </Button>
        </div>
      )}

      {/* ---- Outline Sections Card ---- */}
      {outline?.sections && (
        <div style={cardStyle}>
          <div style={cardTitleStyle}>{t('topic.outlineTitle')}</div>

          {/* Generate Content Banner */}
          {(topic.status === 'outline_ready' || (topic.status === 'content_ready' && pendingLessonCount > 0)) && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 24, padding: '14px 20px',
              background: failedRetryCount > 0 ? DS.warningBg : DS.primaryLight,
              borderRadius: DS.radiusSm,
              borderLeft: `4px solid ${failedRetryCount > 0 ? DS.warning : DS.primary}`,
            }}>
              <Text style={{ fontSize: 13, color: failedRetryCount > 0 ? DS.warning : DS.primary, fontWeight: 500 }}>
                {failedRetryCount > 0
                  ? t('topic.regenerateFailedDesc', { count: failedRetryCount })
                  : topic.status === 'content_ready'
                    ? t('topic.generateNewContentDesc')
                    : t('topic.generateContentDesc')}
              </Text>
              <Button
                type="primary"
                onClick={handleGenerateContent}
                loading={isGenerating}
                icon={<ThunderboltOutlined />}
                style={{
                  borderRadius: DS.radiusSm,
                  background: failedRetryCount > 0 ? DS.warning : DS.primary,
                  borderColor: failedRetryCount > 0 ? DS.warning : DS.primary,
                  fontWeight: 500,
                }}
              >
                {failedRetryCount > 0
                  ? t('topic.regenerateFailed')
                  : t('topic.generateContent')}
              </Button>
            </div>
          )}

          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {outline.sections.map((sec, secIdx) => {
              const generatedLessons = topic?.sections?.find(s => s.title === sec.title)?.lessons || [];
              const doneCount = generatedLessons.filter(l => l.content?.length > 0 && !l.content?.includes('Generation failed')).length;
              const totalCount = sec.lessons.length;
              const allLessonsGenerated = generatedLessons.every(
                l => l.content?.length > 0 && !l.content?.startsWith('[Generation failed:')
              ) && totalCount > 0;
              const sectionId = topic?.sections?.find(s => s.title === sec.title)?.id;

              return (
                <div
                  key={`${secIdx}-${sec.title}`}
                  draggable
                  onDragStart={() => onSectionDragStart(secIdx)}
                  onDragOver={onSectionDragOver}
                  onDragEnd={() => setDragSecIdx(null)}
                  onDrop={() => onSectionDrop(secIdx)}
                  className="topic-section-card"
                  style={{
                    background: DS.cardBg,
                    borderRadius: DS.radiusSm,
                    padding: '20px 24px',
                    border: `1px solid ${DS.borderLight}`,
                    opacity: dragSecIdx === secIdx ? 0.5 : 1,
                    transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
                    boxShadow: 'none',
                  }}>
                  {/* Section Header */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <HolderOutlined
                        className="drag-handle"
                        style={{ cursor: 'grab', color: DS.textMuted, fontSize: 14, opacity: 0.4, transition: 'opacity 0.2s ease' }}
                      />
                      {/* Custom section number badge */}
                      <div style={{
                        minWidth: 28, height: 28, borderRadius: '50%',
                        background: DS.primary,
                        color: '#fff',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13, fontWeight: 600,
                        boxShadow: `0 2px 8px rgba(91, 95, 235, 0.25)`,
                      }}>
                        {secIdx + 1}
                      </div>
                      {editingSectionIdx === secIdx ? (
                        <Space size={4}>
                          <Input
                            size="small"
                            value={editSectionTitle}
                            onChange={(e) => setEditSectionTitle(e.target.value)}
                            onPressEnter={saveEditSection}
                            style={{ width: 200, borderRadius: DS.radiusXs }}
                            autoFocus
                          />
                          <Button size="small" type="text" icon={<CheckOutlined />} onClick={saveEditSection}
                            style={{ color: DS.success }} />
                          <Button size="small" type="text" icon={<CloseOutlined />} onClick={() => setEditingSectionIdx(null)}
                            style={{ color: DS.textSecondary }} />
                        </Space>
                      ) : (
                        <Text strong style={{
                          fontSize: 15,
                          fontWeight: 500,
                          color: DS.text,
                          cursor: 'pointer',
                          letterSpacing: '-0.01em',
                        }}
                          onClick={() => startEditSection(secIdx, sec.title)}>{sec.title}</Text>
                      )}
                      {totalCount > 0 && (
                        <Tag style={{
                          borderRadius: DS.radiusXs,
                          background: doneCount === totalCount ? DS.successBg : DS.borderLight,
                          color: doneCount === totalCount ? DS.success : DS.textSecondary,
                          border: doneCount === totalCount ? `1px solid ${DS.success}33` : `1px solid ${DS.borderLight}`,
                          fontSize: 12,
                          fontWeight: 500,
                        }}>
                          {t('topic.sectionProgress', { done: doneCount, total: totalCount })}
                        </Tag>
                      )}
                    </div>
                    {allLessonsGenerated && sectionId && (
                      (sectionExercises[sectionId] || []).length > 0 ? (
                        <Button
                          size="small"
                          type="primary"
                          ghost
                          icon={<ExperimentOutlined />}
                          onClick={() => {
                            const ex = sectionExercises[sectionId][0];
                            if (ex) navigate(`/topics/${id}/exercise/${ex.id}`);
                          }}
                          style={{ fontSize: 12, borderRadius: DS.radiusXs }}
                        >
                          {t('exercise.startBtn')}
                        </Button>
                      ) : (
                        <Button
                          size="small"
                          type="default"
                          icon={<ExperimentOutlined />}
                          loading={generatingExercise === sectionId}
                          onClick={() => handleGenerateExercise(sectionId)}
                          style={{ fontSize: 12, borderRadius: DS.radiusXs }}
                        >
                          {generatingExercise === sectionId ? t('exercise.generating') : t('exercise.generateBtn')}
                        </Button>
                      )
                    )}
                    <Space size={4}>
                      <Button size="small" type="text" icon={<PlusOutlined />} onClick={() => addLesson(secIdx)}
                        title={t('topic.addLesson')} style={{ color: DS.textSecondary }} />
                      <Popconfirm title={t('topic.deleteSectionConfirm')} onConfirm={() => deleteSection(secIdx)}
                        okText={t('course.confirmDelete')} cancelText={t('topic.cancel')}>
                        <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    </Space>
                  </div>

                  {sec.description && (
                    <Text style={{ color: DS.textSecondary, fontSize: 13, fontStyle: 'italic', marginBottom: 12, display: 'block' }}>
                      {sec.description}
                    </Text>
                  )}

                  {/* Lessons */}
                  <div style={{ marginTop: 8 }}>
                    {sec.lessons.map((les, lesIdx) => {
                      const ls = getLessonStatus(sec.title, les.title);
                      const editKey = `${secIdx}:${lesIdx}`;
                      return (
                        <div
                          key={`${editKey}-${les.title}`}
                          draggable
                          onDragStart={() => onLessonDragStart(secIdx, lesIdx)}
                          onDragOver={onLessonDragOver}
                          onDragEnd={() => setDragLesKey(null)}
                          onDrop={() => onLessonDrop(secIdx, lesIdx)}
                          style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            padding: '8px 14px', marginBottom: 4, borderRadius: DS.radiusXs,
                            background: ls.status === 'generating' ? DS.warningBg
                              : ls.failed ? DS.errorBg
                              : DS.cardBg,
                            border: ls.status === 'generating' ? `1px solid ${DS.warning}33`
                              : ls.failed ? `1px solid ${DS.error}33`
                              : '1px solid transparent',
                            opacity: dragLesKey === `${secIdx}:${lesIdx}` ? 0.5 : 1,
                            transition: 'background 0.2s ease',
                          }}>
                          <Space size={8}>
                            <HolderOutlined
                              className="drag-handle"
                              style={{ cursor: 'grab', color: DS.textMuted, fontSize: 12, opacity: 0.35, transition: 'opacity 0.2s ease' }}
                            />
                            <LessonStatusIcon status={ls.status} failed={ls.failed} />
                            {editingLessonKey === editKey ? (
                              <Space size={4}>
                                <Input
                                  size="small"
                                  value={editLessonTitle}
                                  onChange={(e) => setEditLessonTitle(e.target.value)}
                                  onPressEnter={saveEditLesson}
                                  style={{ width: 180, borderRadius: DS.radiusXs }}
                                  autoFocus
                                />
                                <Button size="small" type="text" icon={<CheckOutlined />} onClick={saveEditLesson}
                                  style={{ color: DS.success }} />
                                <Button size="small" type="text" icon={<CloseOutlined />} onClick={() => setEditingLessonKey(null)}
                                  style={{ color: DS.textSecondary }} />
                              </Space>
                            ) : ls.status === 'generated' && !ls.failed ? (
                              <Text style={{ color: DS.text }}>{les.title}</Text>
                            ) : (
                              <Text
                                style={{ color: DS.text, cursor: 'pointer' }}
                                onClick={() => startEditLesson(secIdx, lesIdx, les.title)}
                              >{les.title}</Text>
                            )}
                          </Space>
                          <Space size={4}>
                            {ls.status === 'generated' && ls.lessonId && !ls.failed && (
                              <Tag
                                style={{
                                  cursor: 'pointer',
                                  borderRadius: DS.radiusXs,
                                  background: DS.successBg,
                                  color: DS.success,
                                  border: `1px solid ${DS.success}33`,
                                  fontWeight: 500,
                                  fontSize: 12,
                                }}
                                onClick={() => navigate(`/topics/${id}/sections/${ls.sectionId}?lesson=${ls.lessonId}`)}
                              >
                                {t('topic.goLearn')} &rarr;
                              </Tag>
                            )}
                            {ls.status === 'generated' && ls.failed && ls.lessonId && (
                              <Button
                                size="small"
                                danger
                                icon={<ReloadOutlined />}
                                loading={retryingLessons.has(ls.lessonId)}
                                onClick={() => handleRetryLesson(ls.lessonId!)}
                                style={{ borderRadius: DS.radiusXs }}
                              >
                                {retryingLessons.has(ls.lessonId) ? t('topic.retrying') : t('topic.retry')}
                              </Button>
                            )}
                            {ls.status === 'generating' && (
                              <Tag style={{
                                borderRadius: DS.radiusXs,
                                background: DS.warningBg,
                                color: DS.warning,
                                border: `1px solid ${DS.warning}33`,
                                fontSize: 12,
                              }}>
                                {t('topic.generating')}
                              </Tag>
                            )}
                            {ls.status === 'pending' && (
                              <Tag style={{
                                borderRadius: DS.radiusXs,
                                color: DS.textMuted,
                                background: '#f9fafb',
                                border: `1px solid ${DS.borderLight}`,
                                fontSize: 12,
                              }}>
                                {t('topic.pending')}
                              </Tag>
                            )}
                            <Popconfirm title={t('topic.deleteLessonConfirm')} onConfirm={() => deleteLesson(secIdx, lesIdx)}
                              okText={t('course.confirmDelete')} cancelText={t('topic.cancel')}>
                              <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                            </Popconfirm>
                          </Space>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </Space>

          {/* Add Section Button */}
          {(topic.status === 'outline_ready' || topic.status === 'content_ready') && (
            <div style={{ marginTop: 20, textAlign: 'center' }}>
              <Button
                type="dashed"
                onClick={addSection}
                icon={<PlusOutlined />}
                block
                style={{
                  borderRadius: DS.radiusSm,
                  borderColor: DS.border,
                  color: DS.textSecondary,
                  height: 44,
                  fontSize: 14,
                  fontWeight: 500,
                }}
              >
                {t('topic.addSection')}
              </Button>
            </div>
          )}

          {/* Feedback Input */}
          {topic.status === 'outline_ready' && (
            <div style={{ marginTop: 24, paddingTop: 20, borderTop: `1px solid ${DS.borderLight}` }}>
              <Input.Search
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                onSearch={handleSendFeedback}
                enterButton={<><SendOutlined /> {t('topic.feedbackBtn')}</>}
                placeholder={langPlaceholder('topic.feedbackPlaceholder', contentLang, topic?.course?.language?.name)}
                loading={isGenerating}
                size="large"
                style={{
                  borderRadius: DS.radiusSm,
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Hover effect styles for drag handles */}
      <style>{`
        .topic-section-card:hover .drag-handle {
          opacity: 1 !important;
        }
        .topic-section-card:hover {
          box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
          border-color: ${DS.border} !important;
        }
      `}</style>
    </AppLayout>
  );
}
