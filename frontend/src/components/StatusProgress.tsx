import { CheckCircleFilled, LoadingOutlined } from '@ant-design/icons';
import { useEffect, useRef, useState } from 'react';

interface Step {
  title: string;
  description: string;
}

interface Props {
  steps: Step[];
  current: number;
  loading?: boolean;
}

const palette = {
  completed: '#5b8c5a',
  completedBg: '#f0f7f0',
  current: '#4f46e5',
  currentBg: '#eef2ff',
  pending: '#d4d4d8',
  pendingText: '#a1a1aa',
  linePending: '#e8e8ea',
  text: '#27272a',
  textMuted: '#71717a',
};

export default function StatusProgress({ steps, current, loading }: Props) {
  const prevCurrent = useRef(current);
  const [animateLine, setAnimateLine] = useState(false);

  useEffect(() => {
    if (current !== prevCurrent.current) {
      setAnimateLine(false);
      requestAnimationFrame(() => setAnimateLine(true));
    }
    prevCurrent.current = current;
  }, [current]);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '28px 16px 24px',
      position: 'relative',
    }}>
      {steps.map((step, i) => {
        const isCompleted = i < current;
        const isCurrent = i === current;
        const isPending = i > current;
        const isActive = isCurrent && loading;

        return (
          <div key={i} style={{
            display: 'flex',
            alignItems: 'center',
            flex: i < steps.length - 1 ? 1 : 'none',
          }}>
            {/* Step node + label */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 10,
              position: 'relative',
              zIndex: 1,
            }}>
              {/* The circle */}
              <div style={{
                width: 52,
                height: 52,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 15,
                fontWeight: 500,
                background: isCompleted
                  ? palette.completedBg
                  : isCurrent
                    ? palette.currentBg
                    : '#fafafa',
                border: `2px solid ${
                  isCompleted ? palette.completed
                    : isCurrent ? palette.current
                    : palette.pending
                }`,
                color: isCompleted
                  ? palette.completed
                  : isCurrent
                    ? palette.current
                    : palette.pendingText,
                boxShadow: isCurrent
                  ? `0 0 0 6px ${palette.currentBg}, 0 2px 12px rgba(79,70,229,0.18)`
                  : isCompleted
                    ? `0 2px 8px rgba(91,140,90,0.12)`
                    : 'none',
                transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                animation: isCurrent && !loading ? 'statusPulse 2.5s ease-in-out infinite' : 'none',
              }}>
                {isActive ? (
                  <LoadingOutlined style={{ fontSize: 22 }} spin />
                ) : isCompleted ? (
                  <CheckCircleFilled style={{ fontSize: 22 }} />
                ) : (
                  <span style={{
                    fontFeatureSettings: '"tnum"',
                    fontVariantNumeric: 'tabular-nums',
                    letterSpacing: '-0.02em',
                  }}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                )}
              </div>

              {/* Labels */}
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  fontSize: 14,
                  fontWeight: isCurrent ? 600 : 500,
                  color: isPending ? palette.pendingText : palette.text,
                  letterSpacing: '-0.01em',
                  marginBottom: 3,
                  transition: 'color 0.4s ease',
                }}>
                  {step.title}
                </div>
                <div style={{
                  fontSize: 12,
                  color: isPending ? palette.pendingText : palette.textMuted,
                  letterSpacing: '-0.005em',
                  maxWidth: 140,
                  lineHeight: 1.4,
                  transition: 'color 0.4s ease',
                }}>
                  {step.description}
                </div>
              </div>
            </div>

            {/* Connecting line */}
            {i < steps.length - 1 && (
              <div style={{
                flex: 1,
                height: 3,
                margin: '0 12px',
                marginTop: -30,
                borderRadius: 2,
                background: palette.linePending,
                overflow: 'hidden',
                position: 'relative',
              }}>
                {/* Filled portion */}
                <div style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  height: '100%',
                  width: isCompleted ? '100%' : '0%',
                  background: `linear-gradient(90deg, ${palette.completed}, ${palette.completed}dd)`,
                  borderRadius: 2,
                  transition: animateLine
                    ? 'width 0.7s cubic-bezier(0.34, 1.56, 0.64, 1)'
                    : 'none',
                }} />

                {/* Glowing dot at the leading edge when completed */}
                {isCompleted && (
                  <div style={{
                    position: 'absolute',
                    right: -2,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    background: palette.completed,
                    boxShadow: `0 0 6px ${palette.completed}`,
                  }} />
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* CSS keyframes */}
      <style>{`
        @keyframes statusPulse {
          0%, 100% { box-shadow: 0 0 0 6px ${palette.currentBg}, 0 2px 12px rgba(79,70,229,0.18); }
          50% { box-shadow: 0 0 0 12px ${palette.currentBg}00, 0 4px 20px rgba(79,70,229,0.28); }
        }
      `}</style>
    </div>
  );
}
