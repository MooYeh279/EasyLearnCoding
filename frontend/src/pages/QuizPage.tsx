import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Spin, message, Popconfirm } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import type { Exercise, ExerciseRunResponse } from '../types';
import ExercisePanel from '../components/ExercisePanel';
import TestRunner from '../components/TestRunner';
import SplitPane from '../components/SplitPane';

const C = {
  pageBg: '#faf9f7',
  primary: '#5b5feb',
  text: '#1e1e24',
  textSec: '#6b7280',
  border: '#e8e8ed',
};

export default function QuizPage() {
  const { topicId, exerciseId } = useParams<{ topicId: string; exerciseId: string }>();
  const navigate = useNavigate();
  const { t } = useContentLang();
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [testResult, setTestResult] = useState<ExerciseRunResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'question' | 'hints' | 'related'>('question');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (exerciseId) {
      api.getExercise(Number(exerciseId))
        .then((ex) => {
          setExercise(ex);
          if (ex.regenerating) {
            setRegenerating(true);
            // Poll until regeneration completes
            pollRef.current = setInterval(() => {
              api.getExercise(Number(exerciseId)).then((fresh) => {
                if (!fresh.regenerating) {
                  clearInterval(pollRef.current!);
                  pollRef.current = null;
                  setExercise(fresh);
                  setRegenerating(false);
                  message.success(t('exercise.regenerateSuccess'));
                }
              });
            }, 2000);
          }
        })
        .catch(() => message.error(t('topic.loadFail')))
        .finally(() => setLoading(false));
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [exerciseId, t]);

  const handleRun = useCallback(async (code: string) => {
    if (!exerciseId) return;
    setRunning(true);
    setTestResult(null);
    try {
      const result = await api.runExercise(Number(exerciseId), code);
      setTestResult(result);
      if (result.error && result.results.length === 0) {
        message.warning(result.error);
      }
    } catch (err: any) {
      const detail = err?.detail || err?.message || 'Run failed';
      setTestResult({ results: [], all_passed: false, error: typeof detail === 'string' ? detail : JSON.stringify(detail), duration_ms: 0 });
    } finally {
      setRunning(false);
    }
  }, [exerciseId]);

  const handleRegenerate = useCallback(async () => {
    if (!exerciseId) return;
    setRegenerating(true);
    setTestResult(null);
    try {
      const updated = await api.regenerateExercise(Number(exerciseId));
      setExercise(updated);
      message.success(t('exercise.regenerateSuccess'));
    } catch {
      message.error(t('exercise.regenerateFail'));
    } finally {
      setRegenerating(false);
    }
  }, [exerciseId, t]);

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />;
  }
  if (!exercise) return null;

  const backUrl = topicId ? `/topics/${topicId}` : '/';

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: C.pageBg }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 24px', background: '#fff', borderBottom: `1px solid ${C.border}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <a onClick={() => navigate(backUrl)} style={{
            cursor: 'pointer', fontSize: 13, color: C.textSec, textDecoration: 'none',
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }}>
            <ArrowLeftOutlined style={{ fontSize: 11 }} />
            {t('exercise.backToTopic')}
          </a>
          <span style={{ color: '#d0d0d8' }}>|</span>
          <span style={{ fontSize: 15, fontWeight: 600, color: C.text }}>{t('exercise.title')}</span>
        </div>
        <Popconfirm
          title={t('exercise.regenerateConfirm')}
          onConfirm={handleRegenerate}
          okText={t('exercise.regenerate')}
          cancelText="—"
          disabled={regenerating}
        >
          <button
            disabled={regenerating}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', fontSize: 13, borderRadius: 6,
              border: `1px solid ${C.border}`, background: '#fff',
              color: regenerating ? C.textSec : C.primary,
              cursor: regenerating ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            <ReloadOutlined spin={regenerating} />
            {regenerating ? t('exercise.regenerating') : t('exercise.regenerate')}
          </button>
        </Popconfirm>
      </div>

      {/* Main content: left + right (resizable split) */}
      <SplitPane
        initialLeft="44%"
        minLeft="280px"
        minRight="340px"
        style={{ flex: 1 }}
      >
        {/* Left panel */}
        <div style={{
          height: '100%', display: 'flex', flexDirection: 'column',
          background: '#fff', borderRight: `1px solid ${C.border}`,
        }}>
          <ExercisePanel
            exercise={exercise}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        </div>

        {/* Right panel */}
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <TestRunner
            exerciseId={Number(exerciseId)}
            template={exercise.template}
            language={exercise.language}
            running={running}
            testResult={testResult}
            onRun={handleRun}
          />
        </div>
      </SplitPane>
    </div>
  );
}
