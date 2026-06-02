import { authFetch } from "./client";
import type { ApiResponse, LoginResponse, User } from "../types/api";

export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  const resp = await authFetch<ApiResponse<LoginResponse>>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return resp.data;
}

export async function register(data: {
  username: string;
  email: string;
  password: string;
  confirm_password: string;
}): Promise<void> {
  await authFetch<ApiResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getMe(): Promise<User> {
  const resp = await authFetch<ApiResponse<User>>("/auth/me");
  return resp.data;
}

export async function changePassword(data: {
  old_password: string;
  new_password: string;
  confirm_password: string;
}): Promise<void> {
  await authFetch<ApiResponse>("/auth/password", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
