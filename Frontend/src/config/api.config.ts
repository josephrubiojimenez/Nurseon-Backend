// Centralized API configuration
export const API_BASE_URL = 'https://nurseon-backend.onrender.com';

// Helper to get user UID
export const getUserId = (): string => {
  return localStorage.getItem('user_uid') || 'mock_user_id';
};

// Generic fetch wrapper with error handling
export const apiFetch = async (endpoint: string, options: RequestInit = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    });

    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }

    return data;
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
};