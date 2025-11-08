import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { CustomerRouteGuard } from './components/CustomerRouteGuard';
import { Layout } from './components/Layout';
import { AdminPage } from './pages/admin/AdminPage';
import { CreatorManagement } from './pages/admin/CreatorManagement';
import { PerformanceUpload } from './pages/uploads/PerformanceUpload';
import { ConversionsUpload } from './pages/uploads/ConversionsUpload';
import { LeaderboardPage } from './pages/dashboard/LeaderboardPage';
import { PlannerPage } from './pages/planner/PlannerPage';
import { HistoricalDataPage } from './pages/analytics/HistoricalDataPage';
import { CampaignForecastPage } from './pages/analytics/CampaignForecastPage';
import { SignUpPage } from './pages/auth/SignUpPage';
import { SignInPage } from './pages/auth/SignInPage';
import { CampaignBuilderPage } from './pages/campaign-builder/CampaignBuilderPage';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Router>
          <Routes>
            {/* Public auth routes */}
            <Route path="/signup" element={<SignUpPage />} />
            <Route path="/signin" element={<SignInPage />} />
            
            {/* Protected customer-facing route (chatbot) */}
            <Route 
              path="/campaign-builder" 
              element={
                <ProtectedRoute>
                  <CampaignBuilderPage />
                </ProtectedRoute>
              } 
            />
            
            {/* Internal app routes (blocked for customer users) */}
            <Route path="/" element={<CustomerRouteGuard><Layout><Navigate to="/dashboard/leaderboard" replace /></Layout></CustomerRouteGuard>} />
            <Route path="/admin" element={<CustomerRouteGuard><Layout><AdminPage /></Layout></CustomerRouteGuard>} />
            <Route path="/admin/creators" element={<CustomerRouteGuard><Layout><CreatorManagement /></Layout></CustomerRouteGuard>} />
            <Route path="/uploads/performance" element={<CustomerRouteGuard><Layout><PerformanceUpload /></Layout></CustomerRouteGuard>} />
            <Route path="/uploads/conversions" element={<CustomerRouteGuard><Layout><ConversionsUpload /></Layout></CustomerRouteGuard>} />
            <Route path="/dashboard/leaderboard" element={<CustomerRouteGuard><Layout><LeaderboardPage /></Layout></CustomerRouteGuard>} />
            <Route path="/planner" element={<CustomerRouteGuard><Layout><PlannerPage /></Layout></CustomerRouteGuard>} />
            <Route path="/analytics/historical" element={<CustomerRouteGuard><Layout><HistoricalDataPage /></Layout></CustomerRouteGuard>} />
            <Route path="/analytics/forecast" element={<CustomerRouteGuard><Layout><CampaignForecastPage /></Layout></CustomerRouteGuard>} />
          </Routes>
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
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
