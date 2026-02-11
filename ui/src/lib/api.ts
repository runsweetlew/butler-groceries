/**
 * API client for DukeCook backend.
 * All calls go through Next.js rewrites → FastAPI.
 */

const API_BASE = '';  // Proxied through Next.js rewrites

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }

  if (res.status === 204) return null as T;
  return res.json();
}

// ---------- Users ----------
export const getUsers = () => request<any[]>('/api/users');

// ---------- Recipes ----------
export const getRecipes = (params?: Record<string, string>) => {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return request<any[]>(`/api/recipes${qs}`);
};
export const getRecipe = (id: number) => request<any>(`/api/recipes/${id}`);
export const createRecipe = (data: any) => request<any>('/api/recipes', { method: 'POST', body: JSON.stringify(data) });
export const updateRecipe = (id: number, data: any) => request<any>(`/api/recipes/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteRecipe = (id: number) => request<void>(`/api/recipes/${id}`, { method: 'DELETE' });
export const getAllTags = () => request<any[]>('/api/recipes/tags/all');
export const archiveRecipe = (id: number) => request<any>(`/api/recipes/${id}/archive`, { method: 'POST' });
export const unarchiveRecipe = (id: number) => request<any>(`/api/recipes/${id}/unarchive`, { method: 'POST' });

// ---------- Import ----------
export const importRecipe = (url: string, userId?: number) =>
  request<any>('/api/recipes/import', { method: 'POST', body: JSON.stringify({ url, user_id: userId }) });
export const bulkImport = (urls: string[], userId?: number) =>
  request<any[]>('/api/recipes/import/bulk', { method: 'POST', body: JSON.stringify({ urls, user_id: userId }) });

export const importFromPhoto = async (file: File, userId?: number): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  if (userId) formData.append('user_id', String(userId));

  const res = await fetch('/api/recipes/import/photo', {
    method: 'POST',
    body: formData,
    // Don't set Content-Type — browser sets multipart boundary automatically
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json();
};

// ---------- Planner ----------
export const getWeekPlan = (start?: string) => {
  const qs = start ? `?start=${start}` : '';
  return request<any>(`/api/planner/week${qs}`);
};
export const addToPlan = (data: any) => request<any>('/api/planner', { method: 'POST', body: JSON.stringify(data) });
export const updatePlan = (id: number, data: any) => request<any>(`/api/planner/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deletePlan = (id: number) => request<void>(`/api/planner/${id}`, { method: 'DELETE' });
export const suggestMeals = (data: any) => request<any>('/api/planner/suggest', { method: 'POST', body: JSON.stringify(data) });
export const addCalendarEvent = (data: any) => request<any>('/api/planner/calendar', { method: 'POST', body: JSON.stringify(data) });
export const deleteCalendarEvent = (id: number) => request<void>(`/api/planner/calendar/${id}`, { method: 'DELETE' });

// ---------- Rules ----------
export const getRules = () => request<any[]>('/api/rules');
export const createRule = (data: any) => request<any>('/api/rules', { method: 'POST', body: JSON.stringify(data) });
export const updateRule = (id: number, data: any) => request<any>(`/api/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteRule = (id: number) => request<void>(`/api/rules/${id}`, { method: 'DELETE' });
export const evaluateRules = (recipeId: number, planDate: string) =>
  request<any[]>(`/api/rules/evaluate?recipe_id=${recipeId}&plan_date=${planDate}`);
export const parseNaturalRule = (text: string) =>
  request<any>('/api/rules/parse', { method: 'POST', body: JSON.stringify({ text }) });

// ---------- Swipe ----------
export const createSwipeSession = (data: any) => request<any>('/api/swipe/sessions', { method: 'POST', body: JSON.stringify(data) });
export const getSwipeSession = (id: number, userId: number) => request<any>(`/api/swipe/sessions/${id}?user_id=${userId}`);
export const getNextCard = (sessionId: number, userId: number) => request<any>(`/api/swipe/sessions/${sessionId}/next?user_id=${userId}`);
export const submitSwipe = (sessionId: number, data: any) =>
  request<any>(`/api/swipe/sessions/${sessionId}/swipe`, { method: 'POST', body: JSON.stringify(data) });
export const getMatches = (sessionId: number) => request<any[]>(`/api/swipe/sessions/${sessionId}/matches`);
export const getActiveSessions = () => request<any[]>('/api/swipe/sessions/active');

// ---------- Ratings ----------
export const createRating = (data: any) => request<any>('/api/ratings', { method: 'POST', body: JSON.stringify(data) });
export const getRecipeRatings = (recipeId: number) => request<any[]>(`/api/ratings/recipe/${recipeId}`);
export const getRatingHistory = (userId?: number, limit?: number) => {
  const params = new URLSearchParams();
  if (userId) params.set('user_id', String(userId));
  if (limit) params.set('limit', String(limit));
  return request<any>(`/api/ratings/history?${params}`);
};
export const getRatingStats = () => request<any>('/api/ratings/stats');

// ---------- Cook-along ----------
export const getCookAlong = (recipeId: number, multiplier?: number) => {
  const qs = multiplier ? `?servings_multiplier=${multiplier}` : '';
  return request<any>(`/api/cookalong/${recipeId}${qs}`);
};
export const getScaledIngredients = (recipeId: number, multiplier?: number) => {
  const qs = multiplier ? `?servings_multiplier=${multiplier}` : '';
  return request<any>(`/api/cookalong/${recipeId}/ingredients${qs}`);
};

// ---------- Shopping ----------
export const getCurrentShoppingList = () => request<any>('/api/shopping/current');
export const generateShoppingList = (data: any) => request<any>('/api/shopping/generate', { method: 'POST', body: JSON.stringify(data) });
export const updateShoppingItem = (itemId: number, data: any) =>
  request<any>(`/api/shopping/items/${itemId}`, { method: 'PUT', body: JSON.stringify(data) });
export const getPantryStaples = () => request<any[]>('/api/shopping/pantry/staples');

// ---------- Kroger ----------
export const getKrogerStatus = (userId: number = 1) =>
  request<any>(`/api/kroger/status?user_id=${userId}`);
export const matchRecipeToKroger = (recipeId: number) =>
  request<any>(`/api/kroger/match/${recipeId}`);
export const addRecipeToKrogerCart = (recipeId: number, userId: number = 1) =>
  request<any>(`/api/kroger/cart/add/${recipeId}?user_id=${userId}`, { method: 'POST' });

// ---------- Taste ----------
export const getTasteProfile = (userId: number) => request<any>(`/api/taste/profile/${userId}`);
export const refreshTasteProfile = (userId: number) => request<any>(`/api/taste/profile/${userId}/refresh`, { method: 'POST' });
export const getTasteInsights = (userId: number) => request<any>(`/api/taste/profile/${userId}/insights`);
export const compareTastes = () => request<any>('/api/taste/compare');
