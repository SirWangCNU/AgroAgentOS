import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import SearchModal from "./SearchModal";
import ToastContainer from "../ui/ToastContainer";
import { useAuthGuard } from "../../hooks/useAuth";
import { usePolling } from "../../hooks/usePolling";
import { useHealthStore } from "../../stores/health";
import { getHealth, getSkills } from "../../api/health";

export default function AppLayout() {
  const { isAuthenticated } = useAuthGuard();
  const setHealth = useHealthStore((s) => s.setHealth);
  const setSkills = useHealthStore((s) => s.setSkills);

  // Poll health every 15 seconds
  usePolling(async () => {
    try {
      const [health, skills] = await Promise.all([getHealth(), getSkills()]);
      setHealth(health);
      setSkills(skills);
    } catch {
      // silently fail
    }
  }, 15000, isAuthenticated);

  if (!isAuthenticated) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-4 bg-bg-main">
          <Outlet />
        </main>
      </div>
      <SearchModal />
      <ToastContainer />
    </div>
  );
}
