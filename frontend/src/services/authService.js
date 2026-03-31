// src/services/authService.js

// 模拟用户数据库（使用 localStorage）
const USERS_KEY = 'charging_station_users';
const CURRENT_USER_KEY = 'charging_station_current_user';

// 初始化用户存储（不创建默认账号）
const initializeUsers = () => {
  const users = localStorage.getItem(USERS_KEY);
  if (!users) {
    localStorage.setItem(USERS_KEY, JSON.stringify([]));
  }
};

// 获取所有用户
const getUsers = () => {
  const users = localStorage.getItem(USERS_KEY);
  return users ? JSON.parse(users) : [];
};

// 保存用户
const saveUsers = (users) => {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
};

// 注册
export const register = (username, password, email, role = 'user') => {
  initializeUsers();
  const users = getUsers();
  
  // 检查用户名是否已存在
  if (users.find(u => u.username === username)) {
    return { success: false, message: '用户名已存在' };
  }
  
  // 检查邮箱是否已存在
  if (users.find(u => u.email === email)) {
    return { success: false, message: '邮箱已被注册' };
  }
  
  const newUser = {
    id: users.length + 1,
    username,
    password, // 实际项目中应该加密
    email,
    role,
    createdAt: new Date().toISOString()
  };
  
  users.push(newUser);
  saveUsers(users);
  
  return { success: true, message: '注册成功', user: { ...newUser, password: undefined } };
};

// 登录
export const login = (username, password) => {
  initializeUsers();
  const users = getUsers();
  const user = users.find(u => u.username === username && u.password === password);
  
  if (!user) {
    return { success: false, message: '用户名或密码错误' };
  }
  
  const userInfo = { ...user, password: undefined };
  localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(userInfo));
  
  return { success: true, message: '登录成功', user: userInfo };
};

// 登出
export const logout = () => {
  localStorage.removeItem(CURRENT_USER_KEY);
};

// 获取当前用户
export const getCurrentUser = () => {
  const user = localStorage.getItem(CURRENT_USER_KEY);
  return user ? JSON.parse(user) : null;
};

// 检查是否已登录
export const isAuthenticated = () => {
  return getCurrentUser() !== null;
};

// 检查是否是管理员
export const isAdmin = () => {
  const user = getCurrentUser();
  return user && user.role === 'admin';
};