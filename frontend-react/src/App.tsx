import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AppLayout from "./components/layout/AppLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";
import Weather from "./pages/Weather";
import Farms from "./pages/Farms";
import Knowledge from "./pages/Knowledge";
import History from "./pages/History";
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
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/farms" element={<Farms />} />
            <Route path="/knowledge" element={<Knowledge />} />
            <Route path="/history" element={<History />} />
            <Route path="/marketing" element={<Marketing />} />
            <Route path="/pest" element={<PestDiagnosis />} />
            <Route path="/users" element={<Users />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
