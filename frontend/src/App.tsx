import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import CourseHome from './pages/CourseHome';
import TopicDetail from './pages/TopicDetail';
import LearningView from './pages/LearningView';
import QuizPage from './pages/QuizPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/courses/:id" element={<CourseHome />} />
        <Route path="/topics/:id" element={<TopicDetail />} />
        <Route path="/topics/:id/sections/:sectionId" element={<LearningView />} />
        <Route path="/topics/:topicId/exercise/:exerciseId" element={<QuizPage />} />
      </Routes>
    </BrowserRouter>
  );
}
