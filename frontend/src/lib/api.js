import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const apiClient = axios.create({ baseURL: API });

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token') || localStorage.getItem('client_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const isAdmin = window.location.pathname.startsWith('/admin');
      if (isAdmin) {
        localStorage.removeItem('admin_token');
        window.location.href = '/admin';
      }
    }
    return Promise.reject(err);
  }
);

// Admin Auth
export const checkSetup = () => apiClient.get('/admin/check-setup');
export const setupAdmin = (data) => apiClient.post('/admin/setup', data);
export const loginAdmin = (data) => apiClient.post('/admin/login', data);
export const getAdminMe = () => apiClient.get('/admin/me');

// Gallery CRUD
export const getGalleries = () => apiClient.get('/admin/galleries');
export const getGallery = (id) => apiClient.get(`/admin/galleries/${id}`);
export const createGallery = (data) => apiClient.post('/admin/galleries', data);
export const updateGallery = (id, data) => apiClient.put(`/admin/galleries/${id}`, data);
export const deleteGallery = (id) => apiClient.delete(`/admin/galleries/${id}`);

// Photo Upload
export const uploadPhotos = (galleryId, files, onProgress) => {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  return apiClient.post(`/admin/galleries/${galleryId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress
  });
};
export const deletePhoto = (galleryId, photoId) =>
  apiClient.delete(`/admin/galleries/${galleryId}/photos/${photoId}`);

// Client Access
export const getGalleryInfo = (slug) => apiClient.get(`/galleries/${slug}`);
export const accessGallery = (slug, password) => apiClient.post(`/galleries/${slug}/access`, { password });
export const getGalleryPhotos = (slug) => {
  const token = localStorage.getItem('client_token');
  return apiClient.get(`/galleries/${slug}/photos`, {
    headers: { Authorization: `Bearer ${token}` }
  });
};
export const toggleFavourite = (slug, photoId) => {
  const token = localStorage.getItem('client_token');
  return apiClient.post(`/galleries/${slug}/favourite`, { photo_id: photoId }, {
    headers: { Authorization: `Bearer ${token}` }
  });
};
export const downloadPhoto = (slug, photoId) => {
  const token = localStorage.getItem('client_token');
  return `${API}/galleries/${slug}/download/${photoId}?token=${token}`;
};
export const downloadZip = (slug, photoIds = []) => {
  const token = localStorage.getItem('client_token');
  return apiClient.post(`/galleries/${slug}/download-zip`, photoIds, {
    headers: { Authorization: `Bearer ${token}` },
    responseType: 'blob'
  });
};

// Media URL helper
export const mediaUrl = (galleryId, path) => `${API}/media/${galleryId}/${path}`;

export default apiClient;
