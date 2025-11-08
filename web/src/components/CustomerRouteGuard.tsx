import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

interface CustomerRouteGuardProps {
  children: React.ReactNode;
}

/**
 * Guard component that redirects authenticated customer users away from internal routes.
 * Internal team can still access these routes directly (they don't use customer auth).
 */
export function CustomerRouteGuard({ children }: CustomerRouteGuardProps) {
  const { isAuthenticated } = useAuth();

  // If user is authenticated via customer auth system, redirect them to campaign builder
  // This prevents customers from accessing internal admin tools
  if (isAuthenticated) {
    return <Navigate to="/campaign-builder" replace />;
  }

  // If not authenticated, allow access (internal team doesn't use customer auth)
  return <>{children}</>;
}

