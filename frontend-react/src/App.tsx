import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AppLayout from "./components/layout/AppLayout";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import Weather from "./pages/Weather";
import Farms from "./pages/Farms";
import Knowledge from "./pages/Knowledge";
import Marketing from "./pages/Marketing";
import PestDiagnosis from "./pages/PestDiagnosis";
import Users from "./pages/Users";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<AppLayout />}>
            {/* Main chat interface — single route with optional param to avoid
                unmount/remount when navigating from /chat to /chat/:sessionId */}
            <Route index element={<Chat />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:sessionId" element={<Chat />} />

            {/* Workspace (Dashboard = landing page for /workspace) */}
            <Route path="/workspace" element={<Dashboard />} />
            <Route path="/workspace/weather" element={<Weather />} />
            <Route path="/workspace/farms" element={<Farms />} />
            <Route path="/workspace/knowledge" element={<Knowledge />} />
            <Route path="/workspace/marketing" element={<Marketing />} />
            <Route path="/workspace/pest" element={<PestDiagnosis />} />
            <Route path="/workspace/users" element={<Users />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
