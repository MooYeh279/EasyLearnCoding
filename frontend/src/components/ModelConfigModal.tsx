import { useEffect, useState } from 'react';
import { Modal, Button, Input, Typography, message } from 'antd';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';

const { Text } = Typography;

const DS = {
  primary: '#5b5feb',
  success: '#10b981',
  error: '#ef4444',
  text: '#1e1e24',
  textSecondary: '#6b7280',
  textMuted: '#9ca3af',
  radiusXs: 8,
};

interface Props {
  open: boolean;
  onClose: () => void;
}

interface TestResult {
  ok: boolean;
  latencyMs: number;
  model: string;
  error?: string;
}

export default function ModelConfigModal({ open, onClose }: Props) {
  const { t } = useContentLang();
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('');
  const [workspacePath, setWorkspacePath] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const loadSettings = async () => {
    setTestResult(null);
    try {
      const [aiData, wsData] = await Promise.all([
        api.getAiSettings(),
        api.getWorkspace(),
      ]);
      setApiKey(aiData.api_key);
      setBaseUrl(aiData.base_url);
      setModel(aiData.model);
      setWorkspacePath(wsData.path);
    } catch {
      message.error('Failed to load settings');
    }
  };

  useEffect(() => {
    if (open) loadSettings();
  }, [open]);

  const handleSave = async () => {
    if (!apiKey.trim() || !baseUrl.trim() || !model.trim()) return;
    setSaving(true);
    try {
      await Promise.all([
        api.updateAiSettings({
          api_key: apiKey.trim(),
          base_url: baseUrl.trim(),
          model: model.trim(),
        }),
        workspacePath.trim() ? api.updateWorkspace(workspacePath.trim()) : Promise.resolve(),
      ]);
      message.success('Settings saved');
      onClose();
    } catch {
      message.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!apiKey.trim() || !baseUrl.trim() || !model.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.testAiConnection({
        api_key: apiKey.trim(),
        base_url: baseUrl.trim(),
        model: model.trim(),
      });
      setTestResult({
        ok: result.ok,
        latencyMs: result.latency_ms,
        model: model.trim(),
        error: result.error,
      });
    } catch {
      setTestResult({ ok: false, latencyMs: 0, model: '', error: 'Request failed' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Modal
      title={
        <span style={{ fontWeight: 600, fontSize: 16, color: DS.text }}>
          {t('model.title')}
        </span>
      }
      open={open}
      onCancel={onClose}
      width={520}
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={onClose} style={{ borderRadius: DS.radiusXs }}>
            {t('model.cancel')}
          </Button>
          <Button
            onClick={handleTest}
            loading={testing}
            style={{ borderRadius: DS.radiusXs }}
          >
            {testing ? t('model.testing') : t('model.testConnection')}
          </Button>
          <Button
            type="primary"
            onClick={handleSave}
            loading={saving}
            style={{ borderRadius: DS.radiusXs, background: DS.primary, borderColor: DS.primary }}
          >
            {t('model.save')}
          </Button>
        </div>
      }
      styles={{ body: { padding: '20px 24px' } }}
    >
      {/* Test result — shown at top of body before form fields */}
      {testResult && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 20,
          padding: '10px 14px',
          borderRadius: DS.radiusXs,
          background: testResult.ok ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
        }}>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 22,
            height: 22,
            borderRadius: '50%',
            background: testResult.ok ? DS.success : DS.error,
            color: '#fff',
            fontSize: 13,
            fontWeight: 700,
            lineHeight: 1,
            flexShrink: 0,
          }}>
            {testResult.ok ? '✓' : '×'}
          </span>
          <span style={{ color: testResult.ok ? DS.success : DS.error, fontSize: 13, fontWeight: 500 }}>
            {testResult.ok ? t('model.testOk') : t('model.testFail')}
          </span>
        </div>
      )}

      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 500, color: DS.text, display: 'block', marginBottom: 6 }}>
          {t('model.apiKey')}
        </label>
        <Input.Password
          value={apiKey}
          onChange={e => { setApiKey(e.target.value); setTestResult(null); }}
          placeholder={t('model.apiKeyPlaceholder')}
          style={{ borderRadius: DS.radiusXs }}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 500, color: DS.text, display: 'block', marginBottom: 6 }}>
          {t('model.baseUrl')}
        </label>
        <Input
          value={baseUrl}
          onChange={e => { setBaseUrl(e.target.value); setTestResult(null); }}
          placeholder={t('model.baseUrlPlaceholder')}
          style={{ borderRadius: DS.radiusXs }}
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 13, fontWeight: 500, color: DS.text, display: 'block', marginBottom: 6 }}>
          {t('model.model')}
        </label>
        <Input
          value={model}
          onChange={e => { setModel(e.target.value); setTestResult(null); }}
          placeholder={t('model.modelPlaceholder')}
          style={{ borderRadius: DS.radiusXs }}
        />
      </div>

      <Text style={{ fontSize: 12, color: DS.textMuted }}>
        {t('model.hint')}
      </Text>

      {/* Divider + Workspace section */}
      <div style={{
        borderTop: '1px solid #e8e8ed',
        margin: '20px 0 14px',
      }} />
      <div style={{ marginBottom: 8 }}>
        <label style={{ fontSize: 13, fontWeight: 500, color: DS.text, display: 'block', marginBottom: 6 }}>
          {t('workspace.path')}
        </label>
        <Input
          value={workspacePath}
          onChange={e => setWorkspacePath(e.target.value)}
          placeholder={t('workspace.placeholder', { defaultPath: '~/.learn-code' })}
          style={{ borderRadius: DS.radiusXs }}
        />
      </div>
      <Text style={{ fontSize: 12, color: DS.textMuted }}>
        {t('workspace.hint')}
      </Text>
    </Modal>
  );
}
