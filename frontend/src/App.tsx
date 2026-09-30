import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LibraryPage } from './pages/LibraryPage';
import { LoginPage } from './pages/LoginPage';

const ReaderPage = lazy(() => import('./pages/ReaderPage').then(module => ({ default: module.ReaderPage })));

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <LibraryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/paper/:id"
            element={
              <ProtectedRoute>
                <Suspense fallback={<div className="p-8 text-center text-slate-500">正在加载阅读器...</div>}>
                  <ReaderPage />
                </Suspense>
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
