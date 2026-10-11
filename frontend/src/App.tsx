import { Route, Routes } from "react-router-dom";

import AppShell from "./components/AppShell";
import { TopicLayout } from "./contexts/TopicContext";
import AboutPage from "./pages/AboutPage";
import BadgesPage from "./pages/BadgesPage";
import DashboardPage from "./pages/DashboardPage";
import HomePage from "./pages/HomePage";
import LabDetailPage from "./pages/LabDetailPage";
import LabsPage from "./pages/LabsPage";
import LessonDetailPage from "./pages/LessonDetailPage";
import LessonsPage from "./pages/LessonsPage";
import NotFoundPage from "./pages/NotFoundPage";
import QuizPage from "./pages/QuizPage";
import ReviewPage from "./pages/ReviewPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="t/:topicSlug" element={<TopicLayout />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="lessons" element={<LessonsPage />} />
          <Route path="lessons/:slug" element={<LessonDetailPage />} />
          <Route
            path="lessons/objective/:objectiveCode"
            element={<LessonDetailPage />}
          />
          <Route path="quiz/:attemptId" element={<QuizPage />} />
          <Route path="mock/:attemptId" element={<QuizPage />} />
          <Route path="review/:attemptId" element={<ReviewPage />} />
          <Route path="labs" element={<LabsPage />} />
          <Route path="labs/:slug" element={<LabDetailPage />} />
          <Route path="badges" element={<BadgesPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
