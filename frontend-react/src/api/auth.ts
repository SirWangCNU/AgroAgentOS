import { authFetch } from "./client";
import type {
  ApiResponse,
  CaptchaChallenge,
  LoginResponse,
  User,
  UserInfo,
} from "../types/api";

export async function getCaptcha(): Promise<CaptchaChallenge> {
  const resp = await authFetch<ApiResponse<CaptchaChallenge>>("/auth/captcha");
  return resp.data;
}

export async function login(
  username: string,
  password: string,
  captchaToken: string,
  captchaAnswer: string
): Promise<LoginResponse> {
  const resp = await authFetch<ApiResponse<LoginResponse>>("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      username,
      password,
      captcha_token: captchaToken,
      captcha_answer: captchaAnswer,
    }),
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

// ==================== 管理员接口 ====================

export async function getUsers(
  page: number = 1,
  pageSize: number = 20
): Promise<{ users: UserInfo[]; total: number }> {
  const resp = await authFetch<ApiResponse<{ users: UserInfo[]; total: number }>>(
    `/auth/users?page=${page}&page_size=${pageSize}`
  );
  return resp.data;
}

export async function adminCreateUser(data: {
  username: string;
  email: string;
  password: string;
  role?: string;
}): Promise<UserInfo> {
  const resp = await authFetch<ApiResponse<UserInfo>>("/auth/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return resp.data;
}

export async function adminUpdateUser(
  userId: number,
  data: { role?: string; is_active?: boolean }
): Promise<UserInfo> {
  const resp = await authFetch<ApiResponse<UserInfo>>(
    `/auth/users/${userId}`,
    {
      method: "PUT",
      body: JSON.stringify(data),
    }
  );
  return resp.data;
}

export async function adminDeleteUser(userId: number): Promise<void> {
  await authFetch<ApiResponse>(`/auth/users/${userId}`, {
    method: "DELETE",
  });
}
