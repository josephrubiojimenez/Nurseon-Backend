
export const loadPersistedState = <T>(key: string, fallback: T): T => {
  if (typeof window === 'undefined') return fallback;

  try {
    const rawValue = window.localStorage.getItem(key);
    if (rawValue === null) return fallback;
    return JSON.parse(rawValue) as T;
  } catch (error) {
    console.warn(`Failed to restore persisted state for ${key}:`, error);
    return fallback;
  }
};

export const savePersistedState = <T>(key: string, value: T) => {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.warn(`Failed to persist state for ${key}:`, error);
  }
};

export const removePersistedState = (key: string) => {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    console.warn(`Failed to remove persisted state for ${key}:`, error);
  }
};
