import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './context/ToastContext';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import AuthModal from './components/AuthModal';

import Landing from './pages/Landing';
import Overview from './pages/Overview';
import NewRepair from './pages/NewRepair';
import RepairStudio from './pages/RepairStudio';
import History from './pages/History';
import Health from './pages/Health';
import Docs from './pages/Docs';

function AppLayout() {
  const { user, isGuest } = useAuth();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Navbar onOpenAuthModal={() => setAuthModalOpen(true)} />

      <div className="flex-1 flex overflow-hidden">
        {/* Only show sidebar if user or guest has entered */}
        {(user || isGuest) && <Sidebar />}

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Routes>
            <Route
              path="/"
              element={
                user || isGuest ? (
                  <Overview />
                ) : (
                  <Landing onOpenAuthModal={() => setAuthModalOpen(true)} />
                )
              }
            />
            <Route path="/overview" element={<Overview />} />
            <Route path="/repair/new" element={<NewRepair />} />
            <Route path="/repair/active" element={<Overview />} />
            <Route path="/repair/:runId" element={<RepairStudio />} />
            <Route path="/history" element={<History />} />
            <Route path="/health" element={<Health />} />
            <Route path="/docs" element={<Docs />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <AppLayout />
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
