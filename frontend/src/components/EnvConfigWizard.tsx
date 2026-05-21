import { useEffect, useState } from 'react';
import { Modal, Button, Typography, Input, message, Space, Tag } from 'antd';
import {
  CheckCircleFilled, CloseCircleFilled, ReloadOutlined,
  CaretRightOutlined, LoadingOutlined, CodeOutlined,
} from '@ant-design/icons';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import type { EnvComponent, EnvState } from '../types';

const { Text } = Typography;

const DS = {
  primary: '#5b5feb',
  success: '#10b981',
  error: '#ef4444',
  text: '#1e1e24',
  textSecondary: '#6b7280',
  textMuted: '#9ca3af',
  border: '#e8e8ed',
  borderLight: '#f0f0f3',
  radiusSm: 10,
  radiusXs: 8,
  codeBg: '#1e1e24',
  codeText: '#e2e8f0',
};

interface Props {
  language: string;
  open: boolean;
  onClose: () => void;
}

interface InstallState {
  [componentName: string]: 'idle' | 'running' | 'done' | 'error';
}

export default function EnvConfigWizard({ language, open, onClose }: Props) {
  const { t } = useContentLang();
  const [step, setStep] = useState(0);
  const [env, setEnv] = useState<EnvState | null>(null);
  const [loading, setLoading] = useState(false);
  const [installState, setInstallState] = useState<InstallState>({});
  const [installOutput, setInstallOutput] = useState<Record<string, string>>({});
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [editableCommands, setEditableCommands] = useState<Record<string, string>>({});

  const loadEnv = async (force = false) => {
    setLoading(true);
    setInstallState({});
    setInstallOutput({});
    try {
      const data = await api.getEnvironment(language, force);
      setEnv(data);
      const vals: Record<string, string> = {};
      for (const field of getConfigFields()) {
        const v = data.config_override?.[field.key];
        if (v) vals[field.key] = v;
      }
      setConfigValues(vals);
      const cmds: Record<string, string> = {};
      data.components.forEach(c => { if (c.install_cmd) cmds[c.name] = c.install_cmd; });
      setEditableCommands(cmds);
    } catch {
      message.error('Failed to check environment');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      setStep(0);
      loadEnv();
    }
  }, [open, language]);

  const missingComponents = env?.components?.filter(c => !c.available) || [];
  const hasMissing = missingComponents.length > 0;

  // Per-language config fields with component-specific labels
  const getConfigFields = (): { key: string; label: string; placeholder: string }[] => {
    const lang = language.toLowerCase();
    if (lang === 'c') {
      return [
        { key: 'runtime_path', label: t('env.gccPathHint'), placeholder: 'e.g. /usr/bin/gcc (Linux) or C:\\mingw64\\bin\\gcc.exe (Windows)' },
        { key: 'compile_flags', label: t('env.compileFlags'), placeholder: '-O2, -Wall, -std=c11' },
      ];
    }
    if (lang === 'cpp') {
      return [
        { key: 'runtime_path', label: t('env.gppPathHint'), placeholder: 'e.g. /usr/bin/g++ (Linux) or C:\\mingw64\\bin\\g++.exe (Windows)' },
        { key: 'compile_flags', label: t('env.compileFlags'), placeholder: '-O2, -Wall, -std=c++17' },
      ];
    }
    if (lang === 'python') {
      return [{ key: 'runtime_path', label: t('env.pythonPathHint'), placeholder: 'e.g. /usr/bin/python3 (Linux) or C:\\Python312\\python.exe (Windows)' }];
    }
    if (lang === 'bash') {
      return [{ key: 'runtime_path', label: t('env.bashPathHint'), placeholder: 'e.g. /bin/bash (Linux) or C:\\Program Files\\Git\\bin\\bash.exe (Windows)' }];
    }
    if (lang === 'typescript') {
      return [
        { key: 'runtime_path', label: t('env.nodePathHint'), placeholder: 'e.g. /usr/bin/node (Linux) or C:\\Program Files\\nodejs\\node.exe (Windows)' },
        { key: 'tsx_path', label: t('env.tsxPathHint'), placeholder: 'e.g. /usr/local/bin/tsx (Linux) or %APPDATA%\\npm\\tsx.cmd (Windows)' },
        { key: 'tsc_path', label: t('env.tscPathHint'), placeholder: 'e.g. /usr/local/bin/tsc (Linux) or %APPDATA%\\npm\\tsc.cmd (Windows)' },
      ];
    }
    // javascript
    return [{ key: 'runtime_path', label: t('env.nodePathHint'), placeholder: 'e.g. /usr/bin/node (Linux) or C:\\Program Files\\nodejs\\node.exe (Windows)' }];
  };

  const runInstall = async (compName: string) => {
    const cmd = editableCommands[compName];
    if (!cmd) return;

    const shellLang = env?.os === 'win' ? 'cmd' : 'bash';
    setInstallState(prev => ({ ...prev, [compName]: 'running' }));
    setInstallOutput(prev => ({ ...prev, [compName]: '' }));

    try {
      await api.runCodeStream(cmd, shellLang, (event, data) => {
        if (event === 'stdout' || event === 'stderr') {
          setInstallOutput(prev => ({
            ...prev,
            [compName]: (prev[compName] || '') + data.text,
          }));
        }
        if (event === 'done') {
          setInstallState(prev => ({
            ...prev,
            [compName]: data.exit_code === 0 ? 'done' : 'error',
          }));
        }
      });
    } catch {
      setInstallState(prev => ({ ...prev, [compName]: 'error' }));
    }
  };

  const handleSaveConfig = async () => {
    // Send all relevant fields for this language; empty string clears the key
    const body: Record<string, string> = {};
    for (const field of getConfigFields()) {
      body[field.key] = configValues[field.key] ?? '';
    }
    await api.updateEnvironment(language, body);
    await loadEnv(true);
    onClose();
  };

  const stepTitles = [t('env.step1Title'), t('env.step2Title'), t('env.step3Title')];

  // ── Step 0: Detection results ────────────────────────────────────

  const renderComponentRow = (comp: EnvComponent) => (
    <div key={comp.name} style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '8px 12px', borderRadius: DS.radiusXs,
      background: comp.available ? '#f0fdf4' : '#fef2f2',
      border: `1px solid ${comp.available ? '#bbf7d0' : '#fecaca'}`,
      marginBottom: 8,
    }}>
      {comp.available
        ? <CheckCircleFilled style={{ color: DS.success, fontSize: 16 }} />
        : <CloseCircleFilled style={{ color: DS.error, fontSize: 16 }} />
      }
      <Text strong style={{ color: comp.available ? DS.success : DS.error, minWidth: 60 }}>
        {comp.name}
      </Text>
      <Text style={{ color: DS.textSecondary, fontSize: 13 }}>
        {comp.available ? comp.version || 'OK' : t('env.notInstalled')}
      </Text>
    </div>
  );

  // ── Step 1: Install guide (shows ALL components) ──────────────────

  const renderInstallBlock = (comp: EnvComponent) => {
    const state = installState[comp.name] || 'idle';
    const output = installOutput[comp.name] || '';

    return (
      <div key={comp.name} style={{
        border: `1px solid ${DS.borderLight}`,
        borderRadius: DS.radiusSm, padding: 16, marginBottom: 12,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Space>
            {comp.available
              ? <CheckCircleFilled style={{ color: DS.success, fontSize: 14 }} />
              : <CloseCircleFilled style={{ color: DS.error, fontSize: 14 }} />
            }
            <Text strong style={{ color: DS.text }}>{comp.name}</Text>
            {comp.available
              ? <Tag style={{ margin: 0, borderRadius: DS.radiusXs, background: '#f0fdf4', color: DS.success, border: '1px solid #bbf7d0', fontSize: 11 }}>{comp.version || 'OK'}</Tag>
              : <Text style={{ color: DS.textSecondary, fontSize: 12 }}>{t('env.notInstalled')}</Text>
            }
          </Space>
          {!comp.available && editableCommands[comp.name] && (
            <Button
              type="primary"
              size="small"
              icon={state === 'running' ? <LoadingOutlined /> : <CaretRightOutlined />}
              onClick={() => runInstall(comp.name)}
              loading={state === 'running'}
              style={{
                borderRadius: DS.radiusXs,
                background: state === 'done' ? DS.success : DS.primary,
                borderColor: state === 'done' ? DS.success : DS.primary,
              }}
            >
              {state === 'running' ? t('env.running')
                : state === 'done' ? 'Done'
                : state === 'error' ? 'Retry'
                : t('env.runCmd')}
            </Button>
          )}
        </div>

        {comp.install_cmd && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: DS.codeBg, borderRadius: DS.radiusXs,
            padding: '4px 4px 4px 12px',
          }}>
            <CodeOutlined style={{ color: DS.textMuted, fontSize: 12 }} />
            <Input
              value={editableCommands[comp.name] || ''}
              onChange={e => setEditableCommands(prev => ({ ...prev, [comp.name]: e.target.value }))}
              variant="borderless"
              style={{
                flex: 1, fontFamily: 'monospace', fontSize: 13,
                background: 'transparent', color: DS.codeText,
              }}
            />
          </div>
        )}

        {output && (
          <pre style={{
            background: '#f8f9fb', borderRadius: DS.radiusXs,
            padding: '8px 12px', fontSize: 12, color: DS.textSecondary,
            maxHeight: 120, overflow: 'auto', marginTop: 8, marginBottom: 0,
          }}>
            {output}
          </pre>
        )}
      </div>
    );
  };

  // ── Step content ──────────────────────────────────────────────────

  const renderStepContent = () => {
    if (!env) return null;

    switch (step) {
      case 0:
        return (
          <div>
            {env.components.map(renderComponentRow)}
            {!hasMissing && (
              <div style={{ textAlign: 'center', padding: '16px 0', color: DS.success }}>
                <CheckCircleFilled style={{ fontSize: 20, marginRight: 8 }} />
                <Text strong style={{ color: DS.success, fontSize: 15 }}>{t('env.allReady')}</Text>
              </div>
            )}
          </div>
        );

      case 1:
        return (
          <div>
            {!hasMissing && (
              <div style={{ textAlign: 'center', padding: '12px 0 20px', color: DS.success }}>
                <CheckCircleFilled style={{ fontSize: 20, marginRight: 8 }} />
                <Text strong style={{ color: DS.success, fontSize: 14 }}>{t('env.allReady')}</Text>
              </div>
            )}
            {hasMissing && (
              <Text style={{ color: DS.textSecondary, fontSize: 13, display: 'block', marginBottom: 16 }}>
                {t('env.componentMissing', { n: missingComponents.length })}
              </Text>
            )}
            {env.components.map(renderInstallBlock)}
          </div>
        );

      case 2:
        return (
          <div>
            {getConfigFields().map(field => (
              <div key={field.key} style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: DS.text, display: 'block', marginBottom: 6 }}>
                  {field.label}
                </label>
                <Input
                  value={configValues[field.key] || ''}
                  onChange={e => setConfigValues(prev => ({ ...prev, [field.key]: e.target.value }))}
                  placeholder={field.placeholder}
                  style={{ borderRadius: DS.radiusXs }}
                />
              </div>
            ))}
            <Text style={{ fontSize: 12, color: DS.textMuted }}>{t('env.leaveEmpty')}</Text>
          </div>
        );
    }
  };

  // ── Footer ────────────────────────────────────────────────────────

  const renderFooter = () => (
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <div>
        {step > 0 && (
          <Button onClick={() => setStep(s => s - 1)} style={{ borderRadius: DS.radiusXs }}>
            {stepTitles[step - 1]}
          </Button>
        )}
      </div>
      <Space>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => loadEnv(true)}
          loading={loading}
          style={{ borderRadius: DS.radiusXs }}
        >
          {t('env.retest')}
        </Button>
        {step === 2 ? (
          <Button
            type="primary"
            onClick={handleSaveConfig}
            style={{ borderRadius: DS.radiusXs, background: DS.primary, borderColor: DS.primary }}
          >
            {t('env.saveAndRetest')}
          </Button>
        ) : step === 1 ? (
          <Button
            type="primary"
            onClick={() => setStep(2)}
            style={{ borderRadius: DS.radiusXs }}
          >
            {t('env.skipInstall')}
          </Button>
        ) : null}
        {step === 0 && (
          <Button
            type="primary"
            onClick={() => setStep(s => s + 1)}
            style={{ borderRadius: DS.radiusXs }}
          >
            {t('env.next')}
          </Button>
        )}
      </Space>
    </div>
  );

  return (
    <Modal
      title={
        <Space>
          <span style={{ fontWeight: 600, fontSize: 16, color: DS.text }}>{t('env.wizardTitle')}</span>
          <Text style={{ color: DS.textMuted, fontSize: 13 }}>— {language}</Text>
          {env?.os && (
            <Tag style={{ margin: 0, borderRadius: DS.radiusXs, fontSize: 11, background: '#eef2ff', color: DS.primary, border: '1px solid #c7d2fe' }}>
              {env.os === 'win' ? 'Windows' : env.os === 'linux' ? 'Linux' : 'macOS'}
            </Tag>
          )}
        </Space>
      }
      open={open}
      onCancel={onClose}
      width={600}
      footer={renderFooter()}
      styles={{ body: { padding: '20px 24px', minHeight: 200 } }}
    >
      {/* Step indicators */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 24, gap: 0,
      }}>
        {stepTitles.map((title, i) => {
          const isActive = i === step;
          const isDone = i < step;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                padding: '4px 12px', borderRadius: DS.radiusXs,
                background: isActive ? '#eef2ff' : 'transparent',
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 600,
                  background: isDone ? DS.success : isActive ? DS.primary : '#e8e8ed',
                  color: isDone ? '#fff' : isActive ? '#fff' : DS.textMuted,
                }}>
                  {isDone ? <CheckCircleFilled style={{ fontSize: 14 }} /> : i + 1}
                </div>
                <Text style={{
                  fontSize: 11, marginTop: 4,
                  color: isActive ? DS.primary : isDone ? DS.success : DS.textMuted,
                  fontWeight: isActive ? 600 : 400,
                }}>{title}</Text>
              </div>
              {i < stepTitles.length - 1 && (
                <div style={{
                  width: 40, height: 2,
                  background: isDone ? DS.success : DS.borderLight,
                  marginBottom: 16,
                }} />
              )}
            </div>
          );
        })}
      </div>

      {renderStepContent()}
    </Modal>
  );
}
