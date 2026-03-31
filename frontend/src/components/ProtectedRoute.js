// src/components/ProtectedRoute.js

import { Navigate } from 'react-router-dom';
import { isAuthenticated, isAdmin, getCurrentUser } from '../services/authService';

export const ProtectedRoute = ({ children, requireAdmin = false }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  
  if (requireAdmin && !isAdmin()) {
    return <Navigate to="/user/map" replace />;
  }
  
  return children;
};

export const PublicRoute = ({ children }) => {
  const user = getCurrentUser();
  
  if (user) {
    if (user.role === 'admin') {
      return <Navigate to="/admin/dashboard" replace />;
    } else {
      return <Navigate to="/user/map" replace />;
    }
  }
  
  return children;
};