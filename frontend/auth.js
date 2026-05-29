/**
 * 前端认证工具模块
 * 封装 JWT token 管理和带认证的 fetch 请求
 */

const AUTH_TOKEN_KEY = 'agro_token';
const AUTH_USER_KEY = 'agro_user';

/**
 * 获取存储的 token
 */
function getToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
}

/**
 * 存储 token
 */
function setToken(token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
}

/**
 * 清除 token 和用户信息
 */
function clearToken() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
}

/**
 * 获取存储的用户信息
 */
function getStoredUser() {
    const userStr = localStorage.getItem(AUTH_USER_KEY);
    if (userStr) {
        try {
            return JSON.parse(userStr);
        } catch (e) {
            return null;
        }
    }
    return null;
}

/**
 * 存储用户信息
 */
function setStoredUser(user) {
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

/**
 * 从服务器获取当前用户信息
 */
async function getCurrentUser() {
    const token = getToken();
    if (!token) return null;

    try {
        const response = await fetch('/api/v1/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            if (data.code === 'SUCCESS') {
                setStoredUser(data.data);
                return data.data;
            }
        }

        // Token 无效，清除
        clearToken();
        return null;
    } catch (e) {
        console.error('获取用户信息失败:', e);
        return null;
    }
}

/**
 * 带 JWT 认证的 fetch 封装
 * 自动附加 Authorization 头，处理 401 错误
 */
async function authFetch(url, options = {}) {
    const token = getToken();

    // 设置默认 headers
    const headers = {
        ...options.headers,
    };

    // 如果有 token，添加 Authorization 头
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // 如果不是 FormData，设置 Content-Type
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    // 处理 401 错误（token 无效或过期）
    if (response.status === 401) {
        clearToken();
        // 如果不在登录页面，跳转到登录页面
        if (!window.location.pathname.includes('login.html')) {
            window.location.href = '/login.html';
        }
        throw new Error('认证失败，请重新登录');
    }

    return response;
}

/**
 * 检查是否已登录
 * 如果未登录，跳转到登录页面
 */
function checkAuth() {
    const token = getToken();
    if (!token) {
        window.location.href = '/login.html';
        return false;
    }
    return true;
}

/**
 * 检查是否是管理员
 */
function isAdmin() {
    const user = getStoredUser();
    return user && user.role === 'admin';
}

/**
 * 退出登录
 */
function logout() {
    clearToken();
    window.location.href = '/login.html';
}

/**
 * 初始化用户菜单
 * 在页面顶部显示用户信息和退出按钮
 */
function initUserMenu() {
    const user = getStoredUser();
    if (!user) return;

    // 查找用户菜单容器
    const menuContainer = document.getElementById('user-menu');
    if (!menuContainer) return;

    // 设置用户名
    const usernameEl = menuContainer.querySelector('.username');
    if (usernameEl) {
        usernameEl.textContent = user.username;
    }

    // 设置角色标签
    const roleEl = menuContainer.querySelector('.role-badge');
    if (roleEl) {
        roleEl.textContent = user.role === 'admin' ? '管理员' : '用户';
        roleEl.className = `role-badge ${user.role === 'admin' ? 'admin' : 'user'}`;
    }

    // 设置头像首字
    const avatarEl = menuContainer.querySelector('.avatar');
    if (avatarEl) {
        avatarEl.textContent = user.username.charAt(0).toUpperCase();
    }

    // 管理员菜单项
    const adminMenuItem = document.getElementById('admin-menu-item');
    if (adminMenuItem) {
        adminMenuItem.style.display = isAdmin() ? 'block' : 'none';
    }
}

// 页面加载时检查认证状态
document.addEventListener('DOMContentLoaded', function() {
    // 如果不在登录页面，检查认证状态
    if (!window.location.pathname.includes('login.html')) {
        const token = getToken();
        if (!token) {
            window.location.href = '/login.html';
            return;
        }

        // 异步获取最新用户信息
        getCurrentUser().then(user => {
            if (user) {
                initUserMenu();
            }
        });
    }
});
