import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Spin } from 'antd';
import { AppstoreOutlined, InboxOutlined, BulbOutlined } from '@ant-design/icons';
import { api } from '../api/client';
import { useContentLang } from '../context/LangContext';
import type { Language, Course } from '../types';
import AppLayout from '../components/AppLayout';

const LANG_DOT_COLORS: Record<string, string> = {
  python: '#3b82f6',
  javascript: '#eab308',
  typescript: '#3b82f6',
  c: '#22c55e',
  'c++': '#ec4899',
  cpp: '#ec4899',
  golang: '#06b6d4',
  go: '#06b6d4',
  rust: '#f97316',
  java: '#ef4444',
  ruby: '#dc2626',
  swift: '#f97316',
  kotlin: '#a855f7',
};

const getLangDotColor = (langName: string): string => {
  const key = langName.toLowerCase().replace(/ /g, '');
  return LANG_DOT_COLORS[key] || '#6b7280';
};

const courseCardStyles = `
.home-page-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
@media (max-width: 960px) {
  .home-page-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .home-page-grid { grid-template-columns: 1fr; }
}

.course-card {
  background: #ffffff;
  border: 1px solid #e8e8ed;
  border-radius: 14px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.course-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 25px rgba(0,0,0,0.08);
  border-color: #5b5feb;
}

.course-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.lang-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.course-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e1e24;
  line-height: 1.4;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.lang-label {
  font-size: 11px;
  font-weight: 500;
  color: #5b5feb;
  background: rgba(91,95,235,0.06);
  padding: 3px 10px;
  border-radius: 20px;
  white-space: nowrap;
  flex-shrink: 0;
}

.topic-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #9ca3af;
  font-size: 13px;
  line-height: 1;
}

.topic-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.topic-tag {
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 6px;
  line-height: 1.6;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.topic-tag-more {
  color: #9ca3af;
  font-size: 12px;
  line-height: 1.6;
}

.empty-state {
  text-align: center;
  padding: 80px 20px 60px;
}
.empty-state h3 {
  font-size: 18px;
  color: #1e1e24;
  margin: 20px 0 8px;
  font-weight: 600;
  letter-spacing: -0.2px;
}
.empty-state p {
  font-size: 14px;
  color: #9ca3af;
  margin: 0;
  line-height: 1.6;
}

.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  font-size: 22px;
  font-weight: 700;
  color: #1e1e24;
  margin: 0;
  letter-spacing: -0.3px;
}
.page-header p {
  font-size: 14px;
  color: #6b7280;
  margin: 4px 0 0;
  line-height: 1.5;
}
`;

export default function HomePage() {
  const navigate = useNavigate();
  const { t } = useContentLang();
  const [languages, setLanguages] = useState<Language[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getLanguages(), api.getCourses()])
      .then(([langs, crs]) => {
        setLanguages(langs);
        setCourses(crs);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <AppLayout>
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
          <Spin size="large" />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <style>{courseCardStyles}</style>

      <div className="page-header">
        <h2>{t('app.title')}</h2>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 10,
          background: 'linear-gradient(135deg, #eef2ff 0%, #faf9ff 100%)',
          border: '1px solid #e0e4f5',
          borderRadius: 10,
          padding: '10px 18px',
          marginTop: 12,
        }}>
          <BulbOutlined style={{ fontSize: 16, color: '#5b5feb' }} />
          <span style={{ fontSize: 13, color: '#4b5563', lineHeight: 1.6 }}>
            {t('home.usageHint')}
          </span>
        </div>
      </div>

      {courses.length === 0 ? (
        <div className="empty-state">
          <InboxOutlined style={{ fontSize: 64, color: '#d4d4d8' }} />
          <h3>No courses found</h3>
          <p>{t('home.noCourses')}</p>
        </div>
      ) : (
        <div className="home-page-grid">
          {courses.map((course) => {
            const lang = languages.find((l) => l.id === course.language_id);
            const topicCount = course.topics?.length || 0;
            const langColor = lang ? getLangDotColor(lang.name) : '#6b7280';

            return (
              <div
                key={course.id}
                className="course-card"
                onClick={() => navigate(`/courses/${course.id}`)}
              >
                <div className="course-card-header">
                  <span
                    className="lang-dot"
                    style={{ backgroundColor: langColor }}
                  />
                  <span className="course-title" title={course.title}>
                    {course.title}
                  </span>
                  {lang && (
                    <span className="lang-label">{lang.display_name}</span>
                  )}
                </div>

                <div className="topic-stat">
                  <AppstoreOutlined style={{ fontSize: 13 }} />
                  <span>
                    {topicCount > 0
                      ? t('home.topicsCount', { n: topicCount })
                      : t('home.noTopics')}
                  </span>
                </div>

                {topicCount > 0 && (
                  <div className="topic-tags-row">
                    {course.topics?.slice(0, 3).map((topic) => (
                      <span key={topic.id} className="topic-tag" title={topic.title}>
                        {topic.title}
                      </span>
                    ))}
                    {topicCount > 3 && (
                      <span className="topic-tag-more">
                        {t('home.more', { n: topicCount - 3 })}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}
