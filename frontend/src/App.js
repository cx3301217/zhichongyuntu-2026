// src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Login';
import UserPage from './components/UserPage';
import AdminDashboard from './components/AdminDashboard';
import { ProtectedRoute } from './components/ProtectedRoute';  // ⭐ 改成命名导入
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          {/* 默认重定向到登录页 */}
          <Route path="/" element={<Navigate to="/login" replace />} />
          
          {/* 登录页 */}
          <Route path="/login" element={<Login />} />
          
          {/* 用户端路由 */}
          <Route
            path="/user/*"
            element={
              <ProtectedRoute>
                <UserPage />
              </ProtectedRoute>
            }
          />
          
          {/* 管理员端路由 */}
          <Route
            path="/admin/*"
            element={
              <ProtectedRoute>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          
          {/* 404 重定向 */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;