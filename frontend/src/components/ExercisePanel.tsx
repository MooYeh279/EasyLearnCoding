import type { Exercise } from '../types';
import { useContentLang } from '../context/LangContext';
import MarkdownRenderer from './MarkdownRenderer';

interface Props {
  exercise: Exercise;
  activeTab: 'question' | 'hints' | 'related';
  onTabChange: (tab: 'question' | 'hints' | 'related') => void;
}

const C = {
  primary: '#5b5feb',
  primaryLight: '#eef0ff',
  text: '#1e1e24',
  textSec: '#6b7280',
  textMuted: '#9ca3af',
  border: '#e8e8ed',
  borderLight: '#f0f0f3',
  radiusSm: 8,
};

export default function ExercisePanel({ exercise, activeTab, onTabChange }: Props) {
  const { t } = useContentLang();

  const tabs: { key: typeof activeTab; labelKey: string }[] = [
    { key: 'question', labelKey: 'exercise.questionTab' },
    { key: 'hints', labelKey: 'exercise.hints' },
    { key: 'related', labelKey: 'exercise.related' },
  ];

  return (
    <>
      {/* Tab bar */}
      <div style={{
        display: 'flex', borderBottom: `1px solid ${C.borderLight}`,
        padding: '0 16px', gap: 0,
      }}>
        {tabs.map(tab => (
          <span
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            style={{
              padding: '10px 16px', fontSize: 13, cursor: 'pointer',
              fontWeight: activeTab === tab.key ? 600 : 400,
              color: activeTab === tab.key ? C.primary : C.textSec,
              borderBottom: activeTab === tab.key ? `2px solid ${C.primary}` : '2px solid transparent',
            }}
          >
            {t(tab.labelKey)}
          </span>
        ))}
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {activeTab === 'question' && (
          <>
            {/* Knowledge tags */}
            {exercise.knowledge_tags && exercise.knowledge_tags.length > 0 && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
                {exercise.knowledge_tags.map(tag => (
                  <span key={tag} style={{
                    background: C.primaryLight, color: C.primary,
                    padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 500,
                  }}>
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {/* Question markdown */}
            <div style={{ fontSize: 14, lineHeight: 1.8 }}>
              <MarkdownRenderer content={exercise.question} />
            </div>
          </>
        )}

        {activeTab === 'hints' && (
          <div>
            {exercise.hints && exercise.hints.length > 0 ? (
              <ul style={{ paddingLeft: 18, fontSize: 14, color: C.textSec, lineHeight: 2.2 }}>
                {exercise.hints.map((hint, i) => (
                  <li key={i}>{hint}</li>
                ))}
              </ul>
            ) : (
              <p style={{ color: C.textMuted, fontSize: 14 }}>{t('exercise.noHints')}</p>
            )}
          </div>
        )}

        {activeTab === 'related' && (
          <div>
            <p style={{ color: C.textSec, fontSize: 14, lineHeight: 1.8 }}>
              {t('exercise.relatedContent')}
            </p>
          </div>
        )}
      </div>
    </>
  );
}
