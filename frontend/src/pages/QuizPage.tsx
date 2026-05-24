import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Spin, message } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import type { Exercise, ExerciseRunResponse } from '../types';
import ExercisePanel from '../components/ExercisePanel';
import TestRunner from '../components/TestRunner';

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
  const [testResult, setTestResult] = useState<ExerciseRunResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'question' | 'hints' | 'related'>('question');

  useEffect(() => {
    if (exerciseId) {
      api.getExercise(Number(exerciseId))
        .then(setExercise)
        .catch(() => message.error(t('topic.loadFail')))
        .finally(() => setLoading(false));
    }
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
      </div>

      {/* Main content: left + right */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left panel */}
        <div style={{
          width: '44%', borderRight: `1px solid ${C.border}`,
          display: 'flex', flexDirection: 'column', background: '#fff',
        }}>
          <ExercisePanel
            exercise={exercise}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        </div>

        {/* Right panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <TestRunner
            exerciseId={Number(exerciseId)}
            template={exercise.template}
            running={running}
            testResult={testResult}
            onRun={handleRun}
          />
        </div>
      </div>
    </div>
  );
}
