import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { AdminPage } from './pages/admin/AdminPage';
import { PerformanceUpload } from './pages/uploads/PerformanceUpload';
import { ConversionsUpload } from './pages/uploads/ConversionsUpload';
import { LeaderboardPage } from './pages/dashboard/LeaderboardPage';
import { PlannerPage } from './pages/planner/PlannerPage';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard/leaderboard" replace />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/uploads/performance" element={<PerformanceUpload />} />
            <Route path="/uploads/conversions" element={<ConversionsUpload />} />
            <Route path="/dashboard/leaderboard" element={<LeaderboardPage />} />
            <Route path="/planner" element={<PlannerPage />} />
          </Routes>
        </Layout>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
