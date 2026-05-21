import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { t as translate } from '../i18n/translations';

export type ContentLanguage = 'zh' | 'en';

interface LangContextType {
  contentLang: ContentLanguage;
  setContentLang: (l: ContentLanguage) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const LangContext = createContext<LangContextType>({
  contentLang: 'zh',
  setContentLang: () => {},
  t: (key: string) => key,
});

export function LangProvider({ children }: { children: ReactNode }) {
  const [contentLang, setContentLang] = useState<ContentLanguage>('zh');
  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => translate(key, contentLang, params),
    [contentLang],
  );
  return (
    <LangContext.Provider value={{ contentLang, setContentLang, t }}>
      {children}
    </LangContext.Provider>
  );
}

export function useContentLang() {
  return useContext(LangContext);
}
