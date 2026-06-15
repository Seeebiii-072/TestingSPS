import api from './api.js';

async function login(email, password) {
  const response = await api.post('/auth/login', { email, password });
  const { access_token, user } = response.data;
  sessionStorage.setItem('token', access_token);
  sessionStorage.setItem('user', JSON.stringify(user));
  return user;
}

async function register(email, full_name, password, role) {
  const response = await api.post('/auth/register', {
    email,
    full_name,
    password,
    role,
  });
  return response.data;
}

function logout() {
  sessionStorage.removeItem('token');
  sessionStorage.removeItem('user');
  window.location.href = '/login';
}

function getCurrentUser() {
  const user = sessionStorage.getItem('user');
  return user ? JSON.parse(user) : null;
}

function isLoggedIn() {
  return !!sessionStorage.getItem('token');
}

const authService = {
  login,
  register,
  logout,
  getCurrentUser,
  isLoggedIn,
};

export default authService;
