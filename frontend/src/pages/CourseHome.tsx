import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Input, Typography, Popconfirm, message, Tooltip } from 'antd';
import { PlusOutlined, ReloadOutlined, SettingOutlined, InfoCircleOutlined, FolderOpenOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import { langPlaceholder } from '../i18n/translations';
import type { Course, Topic, EnvState } from '../types';
import AppLayout from '../components/AppLayout';
import EnvConfigWizard from '../components/EnvConfigWizard';

// ── Design tokens ────────────────────────────────────────────────────
const Tokens = {
  pageBg: '#faf9f7',
  cardBg: '#ffffff',
  primary: '#5b5feb',
  success: '#10b981',
  warning: '#f59e0b',
  error: '#ef4444',
  text: '#1e1e24',
  textSecondary: '#6b7280',
  border: '#e8e8ed',
  borderLight: '#f0f0f3',
  radius: 10,
  radiusSm: 10,
};

// ── Status config ────────────────────────────────────────────────────
interface StatusMeta {
  color: string;
  bg: string;
  pulse?: boolean;
}

const statusMap: Record<string, StatusMeta> = {
  draft:              { color: '#6b7280', bg: '#f3f4f6' },
  generating_outline: { color: '#f59e0b', bg: '#fef9e7', pulse: true },
  generating_content: { color: '#f59e0b', bg: '#fef9e7', pulse: true },
  outline_ready:      { color: '#3b82f6', bg: '#eef2ff' },
  content_ready:      { color: '#10b981', bg: '#ecfdf5' },
};

// ── Pulse keyframe injected once ─────────────────────────────────────
const pulseStyleId = 'coursehome-pulse-keyframes';
if (typeof document !== 'undefined' && !document.getElementById(pulseStyleId)) {
  const style = document.createElement('style');
  style.id = pulseStyleId;
  style.textContent = `
    @keyframes coursehome-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.35; }
    }
  `;
  document.head.appendChild(style);
}

// ── Shared styles ────────────────────────────────────────────────────
const s = {
  envCard: {
    display: 'flex', alignItems: 'center', gap: 12,
    padding: '10px 16px',
    background: '#f8f9fb',
    borderRadius: Tokens.radius,
    border: `1px solid ${Tokens.borderLight}`,
  } as React.CSSProperties,

  envSkeleton: {
    height: 44,
    background: '#f3f4f6',
    borderRadius: Tokens.radius,
  } as React.CSSProperties,

  dot: (color: string, pulse?: boolean) => ({
    width: 8, height: 8, borderRadius: '50%',
    backgroundColor: color,
    flexShrink: 0,
    ...(pulse ? { animation: 'coursehome-pulse 1.8s ease-in-out infinite' } : {}),
  } as React.CSSProperties),

  dotLabel: (color: string) => ({
    fontSize: 12, fontWeight: 500, color,
  } as React.CSSProperties),

  envText: {
    fontSize: 13, color: Tokens.text, fontWeight: 500,
  } as React.CSSProperties,

  envDivider: {
    width: 1, height: 14, background: Tokens.border, flexShrink: 0,
  } as React.CSSProperties,

  envMeta: {
    fontSize: 12, color: Tokens.textSecondary,
  } as React.CSSProperties,

  inputWrapper: {
    background: Tokens.cardBg,
    borderRadius: Tokens.radius + 2,
    border: `1px solid ${Tokens.borderLight}`,
    padding: '2px',
    transition: 'border-color 0.2s, box-shadow 0.2s',
 boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
  } as React.CSSProperties,

  inputHint: {
    fontSize: 12, color: Tokens.textSecondary, marginTop: 8, paddingLeft: 2,
  } as React.CSSProperties,

  topicCard: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 18px',
    background: Tokens.cardBg,
    borderRadius: 12,
    border: `1px solid ${Tokens.borderLight}`,
    marginBottom: 0,
    cursor: 'pointer',
    transition: 'transform 0.18s, box-shadow 0.18s, border-color 0.18s',
    boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
  } as React.CSSProperties,

  topicCardHover: {
    transform: 'translateY(-2px)',
    boxShadow: '0 6px 20px rgba(0,0,0,0.06)',
    borderColor: Tokens.border,
  } as React.CSSProperties,

  topicTitle: {
    fontSize: 16, fontWeight: 500, color: Tokens.text,
  } as React.CSSProperties,

  topicRight: {
    display: 'flex', alignItems: 'center', gap: 14,
    flexShrink: 0,
  } as React.CSSProperties,

  topicStatus: {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '4px 10px',
    borderRadius: 20,
    fontSize: 12, fontWeight: 500,
  } as React.CSSProperties,

  deleteBtn: {
    color: '#f87171', fontSize: 13, fontWeight: 500, padding: 0, height: 'auto',
  } as React.CSSProperties,

  emptyWrap: {
    display: 'flex', flexDirection: 'column' as const,
    alignItems: 'center', justifyContent: 'center',
    padding: '64px 0',
  } as React.CSSProperties,

  emptyIcon: {
    fontSize: 44, color: Tokens.border, marginBottom: 16, opacity: 0.7,
  } as React.CSSProperties,

  emptyText: {
    color: Tokens.textSecondary, fontSize: 14,
  } as React.CSSProperties,

  sectionTitle: {
    fontSize: 14, fontWeight: 600, color: Tokens.text,
    marginBottom: 12, letterSpacing: '0.01em',
  } as React.CSSProperties,

  buttonText: {
    fontSize: 13, fontWeight: 500, color: Tokens.textSecondary,
    padding: '4px 10px', height: 'auto',
  } as React.CSSProperties,

  pageLoader: {
    display: 'flex', flexDirection: 'column' as const,
    alignItems: 'center', justifyContent: 'center',
    height: '60vh', gap: 16,
  } as React.CSSProperties,

  pageLoaderBar: {
    width: 200, height: 4, borderRadius: 2,
    background: `linear-gradient(90deg, ${Tokens.borderLight}, ${Tokens.primary}40, ${Tokens.borderLight})`,
    animation: 'coursehome-pulse 1.6s ease-in-out infinite',
  } as React.CSSProperties,
};

// ══════════════════════════════════════════════════════════════════════
// EnvStatusRow
// ══════════════════════════════════════════════════════════════════════
function EnvStatusRow({ env, onRefresh, onConfigure }: {
  env: EnvState;
  onRefresh: () => void;
  onConfigure: () => void;
}) {
  const { t } = useContentLang();
  const ok = env.ready;
  const dotColor = ok ? Tokens.success : Tokens.error;
  const missingCount = env.components?.filter(c => !c.available).length || 0;

  return (
    <div style={s.envCard}>
      <span style={s.dot(dotColor)} />
      <span style={s.dotLabel(dotColor)}>
        {ok ? t('env.ready') : t('env.notReady')}
      </span>

      {env.components?.map(comp => (
        <span key={comp.name} style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 12, fontWeight: 500,
          color: comp.available ? Tokens.success : Tokens.error,
          background: comp.available ? '#f0fdf4' : '#fef2f2',
          border: `1px solid ${comp.available ? '#bbf7d0' : '#fecaca'}`,
          borderRadius: 16, padding: '2px 10px',
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: comp.available ? Tokens.success : Tokens.error,
          }} />
          {comp.name}
          {comp.version && <span style={{ color: Tokens.textSecondary, fontWeight: 400, marginLeft: 2 }}>{comp.version}</span>}
        </span>
      ))}

      <div style={{ flex: 1 }} />

      {!ok && (
        <span style={{ fontSize: 12, color: Tokens.error, fontWeight: 500 }}>
          {t('env.componentMissing', { n: missingCount })}
        </span>
      )}

      <Tooltip title="Re-check environment">
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined style={{ fontSize: 13 }} />}
          onClick={onRefresh}
          style={{ color: Tokens.textSecondary }}
        />
      </Tooltip>

      <Button
        type="text"
        size="small"
        icon={<SettingOutlined style={{ fontSize: 13 }} />}
        onClick={onConfigure}
        style={s.buttonText}
      >
        {t('env.configure')}
      </Button>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// EnvStatusSkeleton
// ══════════════════════════════════════════════════════════════════════
function EnvStatusSkeleton() {
  return <div style={s.envSkeleton} />;
}

// ══════════════════════════════════════════════════════════════════════
// Page skeleton
// ══════════════════════════════════════════════════════════════════════
function PageLoadingSkeleton() {
  return (
    <div style={s.pageLoader}>
      <FolderOpenOutlined style={{ fontSize: 32, color: Tokens.borderLight }} />
      <div style={s.pageLoaderBar} />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// CourseHome
// ══════════════════════════════════════════════════════════════════════
const { Title } = Typography;

export default function CourseHome() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { contentLang, t } = useContentLang();
  const [course, setCourse] = useState<Course | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [newTitle, setNewTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [env, setEnv] = useState<EnvState | null>(null);
  const [envLoading, setEnvLoading] = useState(true);
  const [configOpen, setConfigOpen] = useState(false);

  // Hover-tracking map for topic cards (topic id -> isHovered)
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  useEffect(() => {
    if (id) {
      api.getCourse(Number(id))
        .then((data) => {
          setCourse(data);
          setTopics(data.topics || []);
        })
        .catch(() => message.error(t('course.loadFail')))
        .finally(() => setPageLoading(false));
    }
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const langName = course?.language?.name;

  const loadEnv = async () => {
    if (!langName) return;
    setEnvLoading(true);
    try {
      const data = await api.getEnvironment(langName);
      setEnv(data);
    } catch { /* ignore */ }
    finally { setEnvLoading(false); }
  };

  useEffect(() => { loadEnv(); }, [langName]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async () => {
    if (!newTitle.trim() || !id) return;
    setLoading(true);
    try {
      const topic = await api.createTopic(Number(id), newTitle.trim());
      setTopics((prev) => [...prev, topic]);
      setNewTitle('');
      message.success(t('course.createSuccess'));
    } catch {
      message.error(t('course.createFail'));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (topicId: number) => {
    try {
      await api.deleteTopic(topicId);
      setTopics((prev) => prev.filter((t) => t.id !== topicId));
      message.success(t('course.deleteSuccess'));
    } catch {
      message.error(t('course.deleteFail'));
    }
  };

  // ── Page loading ──────────────────────────────────────────────────
  if (pageLoading) {
    return (
      <AppLayout breadcrumb={[{ title: t('app.title'), path: '/' }, { title: '...' }]}>
        <PageLoadingSkeleton />
      </AppLayout>
    );
  }

  return (
    <AppLayout breadcrumb={[{ title: t('app.title'), path: '/' }, { title: course?.title || '' }]}>
      {/* ── Environment status ──────────────────────────────────────── */}
      <div style={{ marginBottom: 24 }}>
        {envLoading ? (
          <EnvStatusSkeleton />
        ) : env ? (
          <EnvStatusRow
            env={env}
            onRefresh={loadEnv}
            onConfigure={() => {
              setConfigOpen(true);
            }}
          />
        ) : null}
      </div>

      {/* ── Config wizard ────────────────────────────────────────────── */}
      {langName && (
        <EnvConfigWizard
          language={langName}
          open={configOpen}
          onClose={() => { setConfigOpen(false); loadEnv(); }}
        />
      )}

      {/* ── Topic creation ──────────────────────────────────────────── */}
      <div style={{ marginBottom: 28 }}>
        <div
          style={s.inputWrapper}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor = Tokens.primary + '60';
            (e.currentTarget as HTMLElement).style.boxShadow = `0 0 0 3px ${Tokens.primary}15`;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor = Tokens.borderLight;
            (e.currentTarget as HTMLElement).style.boxShadow = '0 1px 3px rgba(0,0,0,0.04)';
          }}
          onFocusCapture={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor = Tokens.primary + '80';
            (e.currentTarget as HTMLElement).style.boxShadow = `0 0 0 3px ${Tokens.primary}20`;
          }}
          onBlurCapture={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor = Tokens.borderLight;
            (e.currentTarget as HTMLElement).style.boxShadow = '0 1px 3px rgba(0,0,0,0.04)';
          }}
        >
          <Input.Search
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onSearch={handleCreate}
            enterButton={
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 500, fontSize: 14 }}>
                <PlusOutlined /> {t('course.createBtn')}
              </span>
            }
            placeholder={langPlaceholder('course.placeholder', contentLang, course?.language?.name)}
            loading={loading}
            size="large"
            variant="borderless"
            style={{ borderRadius: Tokens.radius }}
          />
        </div>
        <div style={s.inputHint}>
          <InfoCircleOutlined style={{ marginRight: 6, fontSize: 12 }} />
          {t('course.inputHint')}
        </div>
      </div>

      {/* ── Topic list ──────────────────────────────────────────────── */}
      <Title level={5} style={s.sectionTitle}>
        {t('course.topicsTitle', { n: topics.length })}
      </Title>

      {topics.length === 0 ? (
        <div style={s.emptyWrap}>
          <FolderOpenOutlined style={s.emptyIcon} />
          <span style={s.emptyText}>{t('course.noTopics')}</span>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {topics.map((topic) => {
            const meta: StatusMeta = statusMap[topic.status] || statusMap.draft;
            const label = t(`status.${topic.status}`) || topic.status;
            const isHovered = hoveredId === topic.id;

            return (
              <div
                key={topic.id}
                style={{
                  ...s.topicCard,
                  ...(isHovered ? (s.topicCardHover as React.CSSProperties) : {}),
                }}
                onClick={() => navigate(`/topics/${topic.id}`)}
                onMouseEnter={() => setHoveredId(topic.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                {/* Left: title */}
                <span style={s.topicTitle}>{topic.title}</span>

                {/* Right: status + delete */}
                <div style={s.topicRight}>
                  <span style={{
                    ...s.topicStatus,
                    background: meta.bg,
                    color: meta.color,
                  }}>
                    <span style={s.dot(meta.color, meta.pulse)} />
                    {label}
                  </span>

                  <Popconfirm
                    title={t('course.deleteConfirm')}
                    description={t('course.deleteDesc')}
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      handleDelete(topic.id);
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                    okText={t('course.confirmDelete')}
                    cancelText={t('course.cancel')}
                    okButtonProps={{
                      style: { background: Tokens.error, borderColor: Tokens.error, borderRadius: 6 },
                    }}
                    cancelButtonProps={{ style: { borderRadius: 6 } }}
                  >
                    <Button
                      type="text"
                      size="small"
                      style={s.deleteBtn}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {t('course.delete')}
                    </Button>
                  </Popconfirm>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}
