export interface ApiResponse<T = unknown> {
  code: string;
  data: T;
  message?: string;
}

export interface PaginatedData<T> {
  records: T[];
  total: number;
}

export interface User {
  id: number;
  username: string;
  email: string;
  role: "admin" | "user";
  is_active: boolean;
  wx_openid?: string | null;
  nickname?: string | null;
  avatar_url?: string | null;
}

export interface UserInfo extends User {
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface CaptchaChallenge {
  captcha_token: string;
  image_svg: string;
  expires_in: number;
}

export interface HealthData {
  status: string;
  dependencies: {
    milvus: { status: string };
    mcp: { status: string; tools_count: number };
  };
}

export interface Skill {
  name: string;
  display_name: string;
  description: string;
  triggers: string[];
  allowed_tools: string[];
  risk_level: string;
  icon: string;
  category: string;
  tagline: string;
  examples: string[];
}
