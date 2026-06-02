import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../stores/auth";
import { getMe } from "../api/auth";

export function useAuthGuard() {
  const navigate = useNavigate();
  const { token, user, login, logout } = useAuthStore();

  useEffect(() => {
    if (!token) {
      navigate("/login", { replace: true });
      return;
    }

    // Refresh user info on mount
    if (!user) {
      getMe()
        .then((freshUser) => login(token, freshUser))
        .catch(() => logout());
    }
  }, [token, user, login, logout, navigate]);

  return { user, isAuthenticated: !!token };
}
