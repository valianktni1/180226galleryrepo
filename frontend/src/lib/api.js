import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${BACKEND_URL}/api`;

const apiClient = axios.create({ baseURL: API });

apiClient.interceptors.request.use((config) => {
  // Use share_token for share routes, admin_token for admin routes
  const url = config.url || '';
  let token;
  if (url.includes('/share/')) {
    token = localStorage.getItem('share_token');
  } else {
    token = localStorage.getItem('admin_token');
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      if (window.location.pathname.startsWith('/admin')) {
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
export const changePassword = (data) => apiClient.put('/admin/change-password', data);

// Templates
export const getTemplates = () => apiClient.get('/admin/templates');
export const createTemplate = (data) => apiClient.post('/admin/templates', data);
export const updateTemplate = (id, data) => apiClient.put(`/admin/templates/${id}`, data);
export const deleteTemplate = (id) => apiClient.delete(`/admin/templates/${id}`);

// Gallery CRUD
export const getGalleries = (sortBy = 'date_desc') => apiClient.get(`/admin/galleries?sort_by=${sortBy}`);
export const listGalleries = getGalleries;  // Alias
export const getGallery = (id) => apiClient.get(`/admin/galleries/${id}`);
export const createGallery = (data) => apiClient.post('/admin/galleries', data);
export const updateGallery = (id, data) => apiClient.put(`/admin/galleries/${id}`, data);
export const deleteGallery = (id) => apiClient.delete(`/admin/galleries/${id}`);
export const getGalleryStats = (id) => apiClient.get(`/admin/galleries/${id}/stats`);

// Admin Activity Log
export const getAdminActivity = (limit = 50) => apiClient.get(`/admin/activity?limit=${limit}`);

// File Upload
export const uploadFiles = (galleryId, subfolder, files, onProgress) => {
  const formData = new FormData();
  formData.append('subfolder', subfolder);
  files.forEach(f => formData.append('files', f));
  return apiClient.post(`/admin/galleries/${galleryId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
    timeout: 600000,
  });
};
export const deleteFile = (galleryId, fileId) =>
  apiClient.delete(`/admin/galleries/${galleryId}/files/${fileId}`);
export const deleteSubfolder = (galleryId, subfolderName) =>
  apiClient.delete(`/admin/galleries/${galleryId}/subfolders/${encodeURIComponent(subfolderName)}`);
export const setSubfolderCover = (galleryId, subfolderName, fileId) =>
  apiClient.put(`/admin/galleries/${galleryId}/subfolders/${encodeURIComponent(subfolderName)}/cover`, { file_id: fileId });

// Copy files to another subfolder (e.g. Album Favourites)
export const copyToSubfolder = (galleryId, fileIds, targetSubfolder) =>
  apiClient.post(`/admin/galleries/${galleryId}/copy-to-subfolder`, {
    file_ids: fileIds,
    target_subfolder: targetSubfolder
  });

// Download subfolder as zip (streaming, handles 1000+ files)
export const downloadSubfolderZip = (galleryId, subfolder) => {
  const token = localStorage.getItem('admin_token');
  return `${BACKEND_URL}/api/admin/galleries/${galleryId}/download-subfolder?subfolder=${encodeURIComponent(subfolder)}&token=${encodeURIComponent(token)}`;
};

// Admin download single file
export const adminDownloadFile = (galleryId, fileId) => {
  const token = localStorage.getItem('admin_token');
  return fetch(`${BACKEND_URL}/api/admin/galleries/${galleryId}/download-file/${fileId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
};

// Shares
export const createShare = (galleryId, data) =>
  apiClient.post(`/admin/galleries/${galleryId}/shares`, data);
export const getShares = (galleryId) =>
  apiClient.get(`/admin/galleries/${galleryId}/shares`);
export const deleteShare = (shareId) =>
  apiClient.delete(`/admin/shares/${shareId}`);
export const toggleShare = (shareId) =>
  apiClient.put(`/admin/shares/${shareId}/toggle`);
export const updateShareExpiry = (shareId, expiresAt) =>
  apiClient.put(`/admin/shares/${shareId}/expiry`, { expires_at: expiresAt });
export const getShareQR = (shareId) => {
  const baseUrl = window.location.origin;
  return `${API}/admin/shares/${shareId}/qr?base_url=${encodeURIComponent(baseUrl)}`;
};

export const getShareQRFrame = (shareId) => {
  const baseUrl = window.location.origin;
  const token = localStorage.getItem('admin_token');
  return `${API}/admin/shares/${shareId}/qr-frame?base_url=${encodeURIComponent(baseUrl)}&token=${encodeURIComponent(token)}`;
};

// Public Share
export const getShareInfo = (token) => apiClient.get(`/share/${token}`);
export const accessShare = (token, password) =>
  apiClient.post(`/share/${token}/access`, { password, viewer_id: localStorage.getItem(`viewer_id_${token}`) });
export const openAccessShare = (token) => {
  const viewerId = localStorage.getItem(`viewer_id_${token}`);
  const url = viewerId ? `/share/${token}/open-access?viewer_id=${encodeURIComponent(viewerId)}` : `/share/${token}/open-access`;
  return apiClient.get(url);
};
export const getShareFiles = (token) =>
  apiClient.get(`/share/${token}/files`);
export const toggleShareFavourite = (token, fileId) =>
  apiClient.post(`/share/${token}/favourite`, { file_id: fileId });
export const submitFavouritesToAlbum = (token) =>
  apiClient.post(`/share/${token}/submit-favourites`);
export const downloadShareFile = (token, fileId) => {
  const jwt = localStorage.getItem('share_token');
  return fetch(`${BACKEND_URL}/api/share/${token}/download/${fileId}`, {
    headers: { Authorization: `Bearer ${jwt}` }
  });
};
export const downloadShareZip = (token, fileIds = []) =>
  apiClient.post(`/share/${token}/download-zip`, fileIds, {
    responseType: 'blob',
    timeout: 600000,
  });

// Direct download URL for share albums (better for large files)
export const getShareDownloadUrl = (token, subfolder = null) => {
  const jwt = localStorage.getItem('share_token');
  let url = `${BACKEND_URL}/api/share/${token}/download-album?t=${encodeURIComponent(jwt)}`;
  if (subfolder) {
    url += `&subfolder=${encodeURIComponent(subfolder)}`;
  }
  return url;
};

// Direct download URL for favourites
export const getShareFavouritesDownloadUrl = (token) => {
  const jwt = localStorage.getItem('share_token');
  return `${BACKEND_URL}/api/share/${token}/download-favourites?t=${encodeURIComponent(jwt)}`;
};
export const guestUpload = (token, files, onProgress) => {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  return apiClient.post(`/share/${token}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
    timeout: 600000,
  });
};
export const guestDeleteFiles = (token, fileIds) =>
  apiClient.post(`/share/${token}/delete`, { file_ids: fileIds });

// Admin Print Shop
export const getPrintSizes = () => apiClient.get('/admin/print-sizes');
export const createPrintSize = (data) => apiClient.post('/admin/print-sizes', data);
export const updatePrintSize = (id, data) => apiClient.put(`/admin/print-sizes/${id}`, data);
export const deletePrintSize = (id) => apiClient.delete(`/admin/print-sizes/${id}`);
export const getPrintOrders = () => apiClient.get('/admin/print-orders');
export const updateOrderStatus = (orderId, status) => 
  apiClient.put(`/admin/print-orders/${orderId}/status?status=${status}`);

// Public Print Shop (for couples)
export const getSharePrintSizes = (token) =>
  apiClient.get(`/share/${token}/print-sizes`);
export const createPrintOrder = (token, data) =>
  apiClient.post(`/share/${token}/print-order`, data);
export const updatePrintOrderPaypal = (token, orderId, paypalOrderId, status = 'paid') =>
  apiClient.put(`/share/${token}/print-order/${orderId}/paypal?paypal_order_id=${paypalOrderId}&status=${status}`);
export const getMyPrintOrders = (token) =>
  apiClient.get(`/share/${token}/print-orders`);

// Activity tracking
export const trackGalleryView = (token) =>
  apiClient.post(`/share/${token}/track-view`).catch(() => {});
export const trackDownload = (token) =>
  apiClient.post(`/share/${token}/track-download`).catch(() => {});

// Media URL helpers
export const thumbUrl = (galleryId, subfolder, filename) => {
  const stem = filename.replace(/\.[^/.]+$/, '');
  const sfSlug = subfolder.toLowerCase().replace(/ /g, '-').replace(/&/g, 'and');
  return `${API}/media/thumb/${galleryId}/${sfSlug}/${stem}.thumb.jpg`;
};
export const previewUrl = (galleryId, subfolder, filename) => {
  const stem = filename.replace(/\.[^/.]+$/, '');
  const sfSlug = subfolder.toLowerCase().replace(/ /g, '-').replace(/&/g, 'and');
  return `${API}/media/preview/${galleryId}/${sfSlug}/${stem}.preview.jpg`;
};

export default apiClient;
