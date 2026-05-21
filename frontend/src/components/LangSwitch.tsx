import { Segmented } from 'antd';
import { useContentLang, type ContentLanguage } from '../context/LangContext';

export default function LangSwitch() {
  const { contentLang, setContentLang } = useContentLang();
  return (
    <Segmented
      size="small"
      value={contentLang}
      onChange={(v) => setContentLang(v as ContentLanguage)}
      options={[
        { label: '中文', value: 'zh' },
        { label: 'English', value: 'en' },
      ]}
      style={{
        background: 'rgba(255,255,255,0.08)',
        color: '#fff',
        borderRadius: 8,
      }}
    />
  );
}
