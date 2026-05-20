import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Deploy from './pages/Deploy';
import AppDetail from './pages/AppDetail';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/deploy" element={<Deploy />} />
        <Route path="/apps/:id" element={<AppDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
