import { useState, type ReactNode } from 'react';
import { Button, Layout, Typography } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import LangSwitch from './LangSwitch';
import ModelConfigModal from './ModelConfigModal';
import { useContentLang } from '../context/LangContext';

const { Header, Content } = Layout;
const { Text } = Typography;

interface Props {
  title?: string;
  subtitle?: string;
  breadcrumb?: { title: string; path?: string }[];
  children: ReactNode;
}

const headerGradient = 'linear-gradient(135deg, #1a1a24 0%, #1e1e2e 100%)';

const brandStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  cursor: 'pointer',
};

const monogramStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 28,
  height: 28,
  borderRadius: '50%',
  background: '#5b5feb',
  color: '#fff',
  fontSize: 14,
  fontWeight: 600,
  lineHeight: 1,
  flexShrink: 0,
};

const brandNameStyle: React.CSSProperties = {
  color: '#fff',
  fontSize: 15,
  fontWeight: 300,
  letterSpacing: '0.05em',
  whiteSpace: 'nowrap',
};

const breadcrumbSepStyle: React.CSSProperties = {
  color: 'rgba(255,255,255,0.25)',
  margin: '0 6px',
  fontSize: 12,
  userSelect: 'none',
};

const breadcrumbPathStyle: React.CSSProperties = {
  color: 'rgba(255,255,255,0.5)',
  cursor: 'pointer',
  fontSize: 13,
};

const breadcrumbCurrentStyle: React.CSSProperties = {
  color: '#fff',
  fontSize: 13,
};

export default function AppLayout({ breadcrumb, children }: Props) {
  const navigate = useNavigate();
  const { t } = useContentLang();
  const [modelOpen, setModelOpen] = useState(false);

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header style={{
        background: headerGradient,
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 56,
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <a onClick={() => navigate('/')} style={brandStyle}>
            <span style={monogramStyle}>L</span>
            <span style={brandNameStyle}>LearnCoding</span>
          </a>
          {breadcrumb && (
            <div style={{ display: 'flex', alignItems: 'center' }}>
              {breadcrumb.map((item, i) => (
                <span key={i} style={{ display: 'flex', alignItems: 'center' }}>
                  {i > 0 && <Text style={breadcrumbSepStyle}>/</Text>}
                  {item.path ? (
                    <a onClick={() => navigate(item.path!)} style={breadcrumbPathStyle}>
                      {item.title}
                    </a>
                  ) : (
                    <Text style={breadcrumbCurrentStyle}>{item.title}</Text>
                  )}
                </span>
              ))}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button
            type="text"
            size="small"
            icon={<SettingOutlined style={{ fontSize: 14, color: 'rgba(255,255,255,0.6)' }} />}
            onClick={() => setModelOpen(true)}
            style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12 }}
          >
            {t('model.title')}
          </Button>
          <LangSwitch />
        </div>
      </Header>
      <ModelConfigModal open={modelOpen} onClose={() => setModelOpen(false)} />
      <Content style={{
        padding: '32px 40px',
        maxWidth: 1100,
        margin: '0 auto',
        width: '100%',
        background: '#faf9f7',
      }}>
        {children}
      </Content>
    </Layout>
  );
}
