import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ChatView from './views/ChatView';
import AdminView from './views/AdminView';
import ClinicalView from './views/ClinicalView';
import { useAppStore } from './store/useAppStore';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const App: React.FC = () => {
  const fetchInitialData = useAppStore((state) => state.fetchInitialData);
  const isInitialized = useAppStore((state) => state.isInitialized);

  useEffect(() => {
    if (!isInitialized) {
      fetchInitialData();
    }
  }, [isInitialized, fetchInitialData]);

  return (
    <Router>
      <Routes>
        <Route path="/" element={<ChatView />} />
        <Route path="/admin/*" element={<AdminView />} />
        <Route path="/clinical" element={<ClinicalView />} />
      </Routes>
      <ToastContainer position="bottom-right" theme="dark" />
    </Router>
  );
};

export default App;