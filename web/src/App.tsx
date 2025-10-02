import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
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
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#363636',
              color: '#fff',
            },
            success: {
              duration: 3000,
              iconTheme: {
                primary: '#10B981',
                secondary: '#fff',
              },
            },
            error: {
              duration: 5000,
              iconTheme: {
                primary: '#EF4444',
                secondary: '#fff',
              },
            },
          }}
        />
      </Router>
    </QueryClientProvider>
  );
}

export default App;
