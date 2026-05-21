import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { LangProvider } from './context/LangContext'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#5b5feb',
          colorSuccess: '#10b981',
          colorWarning: '#f59e0b',
          colorError: '#ef4444',
          colorInfo: '#5b5feb',
          colorTextBase: '#1e1e24',
          colorBgBase: '#ffffff',
          borderRadius: 10,
          borderRadiusSM: 6,
          borderRadiusLG: 14,
          fontFamily:
            "'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif",
          fontSize: 14,
          lineHeight: 1.6,
          controlHeight: 36,
          paddingContentHorizontal: 20,
          paddingContentVertical: 16,
        },
        components: {
          Layout: {
            headerBg: '#1a1a24',
            headerHeight: 56,
            bodyBg: '#faf9f7',
            siderBg: '#ffffff',
          },
          Card: {
            paddingLG: 24,
            padding: 20,
            borderRadiusLG: 14,
          },
          Button: {
            borderRadius: 8,
            controlHeight: 36,
            primaryShadow: '0 2px 8px rgba(91,95,235,0.25)',
          },
          Tag: {
            borderRadiusSM: 5,
          },
          Menu: {
            itemBorderRadius: 8,
            itemMarginInline: 6,
          },
          Input: {
            borderRadius: 8,
            controlHeight: 38,
          },
          Select: {
            borderRadius: 8,
          },
          Segmented: {
            borderRadius: 8,
          },
          Modal: {
            borderRadiusLG: 14,
          },
        },
      }}
    >
      <LangProvider>
        <App />
      </LangProvider>
    </ConfigProvider>
  </StrictMode>,
)
