import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle
} from "@/components/ui/alert-dialog";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  ArrowLeft, Upload, Trash2, Copy, FolderOpen, Share2, QrCode,
  MoreVertical, Link, Lock, Globe, Image as ImageIcon, Film, Check,
  Download, Plus, X, Heart, Calendar as CalendarIcon, Clock, Star, FileText, Mail, Send, Palette, RefreshCw, Pencil, Paperclip,
  AlertTriangle, CheckCircle2, ShieldCheck, XCircle, BookOpen, Unlock, History
} from "lucide-react";
import {
  getGallery, uploadFiles, deleteFile, createSubfolder, deleteSubfolder, copyToSubfolder, adminDownloadFile,
  createShare, deleteShare, toggleShare, updateShareExpiry, updateShare, getShareQR, getShareQRFrame, getQRDesignPreview, thumbUrl, setSubfolderCover,
  updateGallery, getGalleryReadiness, sendGalleryNotification, getEmailTemplates, sendTemplateEmail, sendGalleryEmail, sendQrPickerEmail, getVideoHealth,
  startAdminFolderDownload, getAdminFolderDownloadStatus, getDownloadJobFileUrl, getErrorMessage,
  updateAlbumSelection, reopenAlbumSelection, sendAlbumSelectionInvitation
} from "@/lib/api";
import { THEME_LIST } from "@/lib/themes";
import DownloadJobProgress from "@/components/DownloadJobProgress";
import AdminThemeToggle from "@/components/AdminThemeToggle";
import SecureAudioPlayer from "@/components/SecureAudioPlayer";

const STANDARD_SUBFOLDERS = ["Wedding Images", "Video", "SelfieBooth", "Album Favourites", "Guest Uploads"];
const THUMBNAIL_FILE_TYPES = new Set(["photo", "video"]);
const THUMBNAIL_POLL_MAX_ATTEMPTS = 60;

export default function AdminGalleryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const attachmentInputRef = useRef(null);

  const [gallery, setGallery] = useState(null);
  const [files, setFiles] = useState([]);
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [downloading, setDownloading] = useState(false);
  const [downloadJob, setDownloadJob] = useState(null);
  const downloadPollRef = useRef(null);
  const downloadStartedRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [copying, setCopying] = useState(false);
  const [selectMode, setSelectMode] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [reprocessProgress, setReprocessProgress] = useState(null);
  const [transcodeStatus, setTranscodeStatus] = useState({});  // file_id -> {percent, status, method, filename}
  const transcodePollingRef = useRef(null);
  const [sendingNotification, setSendingNotification] = useState(false);
  const [checkingReadiness, setCheckingReadiness] = useState(false);
  const [showReadiness, setShowReadiness] = useState(false);
  const [galleryReadiness, setGalleryReadiness] = useState(null);
  const [editingEmail, setEditingEmail] = useState(false);
  const [clientEmail, setClientEmail] = useState("");
  const [galleryTheme, setGalleryTheme] = useState("classic_gold");
  const thumbPollingRef = useRef(null);
  const thumbPollAttemptsRef = useRef(0);

  // Send Template Email
  const [showSendEmail, setShowSendEmail] = useState(false);
  const [emailTemplates, setEmailTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [sendingTemplate, setSendingTemplate] = useState(false);
  const [galleryEmailAttachments, setGalleryEmailAttachments] = useState([]);
  const [sendingQrPicker, setSendingQrPicker] = useState(false);
  const [updatingAlbumPlan, setUpdatingAlbumPlan] = useState(false);
  const [sendingAlbumInvitation, setSendingAlbumInvitation] = useState(false);

  // Video health check
  const [videoHealth, setVideoHealth] = useState(null); // { videos: [], summary: {} }

  // Share creation
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [shareForm, setShareForm] = useState({
    subfolder: null, password: "", access_level: "download", label: "", expires_at: null, custom_slug: "", guest_upload_mode: false, allow_all_file_types: false
  });
  const [creatingShare, setCreatingShare] = useState(false);

  // Expiry date picker
  const [expiryPickerOpen, setExpiryPickerOpen] = useState(false);

  // QR display
  const [showQR, setShowQR] = useState(null);
  const [editingShare, setEditingShare] = useState(null);
  const [editForm, setEditForm] = useState({ password: '', label: '', access_level: '' });

  // Subfolder delete confirmation
  const [deleteSubfolderTarget, setDeleteSubfolderTarget] = useState(null);

  // Add subfolder
  const [showAddFolderDialog, setShowAddFolderDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [creatingFolder, setCreatingFolder] = useState(false);

  // File/bulk delete confirmation with backup option
  const [fileDeleteConfirm, setFileDeleteConfirm] = useState({ open: false, fileId: null, filename: "", deleteBackup: false, isBulk: false });

  const loadGallery = useCallback(async () => {
    try {
      const res = await getGallery(id);
      setGallery(res.data);
      setFiles(res.data.files || []);
      setShares(res.data.shares || []);
      setClientEmail(res.data.client_email || "");
      setGalleryTheme(res.data.theme || "classic_gold");
      if (res.data.subfolders?.length) {
        setActiveTab(currentTab => currentTab || res.data.subfolders[0]);
      }
    } catch {
      toast.error("Gallery not found");
      navigate("/admin/dashboard");
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) { navigate("/admin"); return; }
    loadGallery();
  }, [navigate, loadGallery]);

  // Fetch video health status when gallery loads
  const loadVideoHealth = useCallback(async () => {
    try {
      const res = await getVideoHealth(id);
      setVideoHealth(res.data);
    } catch { /* ignore - non-critical */ }
  }, [id]);

  useEffect(() => {
    if (gallery) loadVideoHealth();
  }, [gallery, loadVideoHealth]);

  // Poll transcode status
  const startTranscodePolling = useCallback(() => {
    if (transcodePollingRef.current) return;
    transcodePollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/admin/galleries/${id}/transcode-status`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('admin_token')}` }
        });
        const data = await res.json();
        if (data.active) {
          setTranscodeStatus(data.files);
        } else {
          setTranscodeStatus({});
          clearInterval(transcodePollingRef.current);
          transcodePollingRef.current = null;
        }
      } catch { /* ignore poll errors */ }
    }, 2000);
  }, [id]);

  useEffect(() => {
    return () => {
      if (transcodePollingRef.current) {
        clearInterval(transcodePollingRef.current);
        transcodePollingRef.current = null;
      }
      if (thumbPollingRef.current) {
        clearInterval(thumbPollingRef.current);
        thumbPollingRef.current = null;
      }
      thumbPollAttemptsRef.current = 0;
      if (downloadPollRef.current) {
        clearTimeout(downloadPollRef.current);
        downloadPollRef.current = null;
      }
    };
  }, []);

  // Auto-refresh when files are missing thumbnails (e.g. after bulk upload)
  useEffect(() => {
    // Audio and document records never receive thumbnails. Restrict polling to
    // media that actually enters the thumbnail worker, and cap the retries so
    // one failed image/video can never refresh a large gallery forever.
    const missingThumbs = files.some(f => THUMBNAIL_FILE_TYPES.has(f.file_type) && !f.has_thumb);
    if (missingThumbs && !thumbPollingRef.current) {
      thumbPollAttemptsRef.current = 0;
      thumbPollingRef.current = setInterval(() => {
        thumbPollAttemptsRef.current += 1;
        if (thumbPollAttemptsRef.current > THUMBNAIL_POLL_MAX_ATTEMPTS) {
          clearInterval(thumbPollingRef.current);
          thumbPollingRef.current = null;
          return;
        }
        loadGallery();
      }, 5000);
    } else if (!missingThumbs && thumbPollingRef.current) {
      clearInterval(thumbPollingRef.current);
      thumbPollingRef.current = null;
      thumbPollAttemptsRef.current = 0;
    }
  }, [files, loadGallery]);

  const handleUpload = async (fileList) => {
    if (!fileList?.length || !activeTab) return;
    setUploading(true);
    setUploadProgress(0);
    try {
      const arr = Array.from(fileList);
      const hasVideos = arr.some(f => /\.(mp4|mov|avi|mkv|wmv|webm|m4v|flv|mts|m2ts)$/i.test(f.name));
      const res = await uploadFiles(id, activeTab, arr, (e) => {
        setUploadProgress(Math.round((e.loaded * 100) / e.total));
      });
      toast.success(`${arr.length} file(s) uploaded to ${activeTab}`);
      // Show auto-share notification if one was created
      if (res.data?.auto_share) {
        const s = res.data.auto_share;
        toast.success(`Share link auto-created: /${s.token} (pw: ${s.password})`, { duration: 10000 });
      }
      loadGallery();
      if (hasVideos) {
        setTimeout(() => startTranscodePolling(), 3000);
      }
    } catch (err) {
      toast.error("Upload failed");
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const handleDeleteSubfolder = async (sfName) => {
    // Opens confirmation dialog
    setDeleteSubfolderTarget(sfName);
  };

  const confirmDeleteSubfolder = async () => {
    const sfName = deleteSubfolderTarget;
    if (!sfName) return;
    setDeleteSubfolderTarget(null);
    try {
      const res = await deleteSubfolder(id, sfName);
      toast.success(`"${sfName}" removed`);
      if (activeTab === sfName) {
        setActiveTab(res.data.subfolders?.[0] || "");
      }
      loadGallery();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete subfolder");
    }
  };

  const handleCreateSubfolder = async () => {
    const name = newFolderName.trim();
    if (!name) {
      toast.error("Enter a folder name");
      return;
    }

    setCreatingFolder(true);
    try {
      const res = await createSubfolder(id, name);
      setGallery(current => ({
        ...current,
        subfolders: res.data.subfolders,
        file_counts: res.data.file_counts,
      }));
      setActiveTab(res.data.subfolder);
      setNewFolderName("");
      setShowAddFolderDialog(false);
      toast.success(`"${res.data.subfolder}" added`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to add folder");
    } finally {
      setCreatingFolder(false);
    }
  };

  const handleDeleteFile = async (fileId) => {
    const file = files.find(f => f.id === fileId);
    setFileDeleteConfirm({ open: true, fileId, filename: file?.filename || "this file", deleteBackup: false, isBulk: false });
  };

  const handleBulkDelete = async () => {
    setFileDeleteConfirm({ open: true, fileId: null, filename: `${selectedFiles.size} selected files`, deleteBackup: false, isBulk: true });
  };

  const confirmFileDelete = async () => {
    const { fileId, deleteBackup, isBulk } = fileDeleteConfirm;
    if (isBulk) {
      for (const fid of selectedFiles) {
        try { await deleteFile(id, fid, deleteBackup); } catch (e) { /* skip */ }
      }
      toast.success(`${selectedFiles.size} files deleted${deleteBackup ? " (+ backups)" : ""}`);
      setSelectedFiles(new Set());
      setSelectMode(false);
    } else {
      try {
        await deleteFile(id, fileId, deleteBackup);
        toast.success(deleteBackup ? "File and backup deleted" : "File deleted");
      } catch { toast.error("Failed to delete"); }
    }
    setFileDeleteConfirm({ open: false, fileId: null, filename: "", deleteBackup: false, isBulk: false });
    loadGallery();
  };

  const handleCopyToFavourites = async () => {
    if (selectedFiles.size === 0) return;
    if (!gallery.subfolders.includes("Album Favourites")) {
      toast.error("Album Favourites folder doesn't exist in this gallery");
      return;
    }
    setCopying(true);
    try {
      const res = await copyToSubfolder(id, Array.from(selectedFiles), "Album Favourites");
      toast.success(`${res.data.copied} files copied to Album Favourites`);
      setSelectedFiles(new Set());
      setSelectMode(false);
      loadGallery();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to copy");
    } finally {
      setCopying(false);
    }
  };

  const pollAdminDownload = (jobId, ticket) => {
    const check = async () => {
      try {
        const response = await getAdminFolderDownloadStatus(jobId);
        const nextJob = { ...response.data, ticket };
        setDownloadJob(nextJob);

        if (nextJob.status === "ready" && downloadStartedRef.current !== jobId) {
          downloadStartedRef.current = jobId;
          const link = document.createElement("a");
          link.href = getDownloadJobFileUrl(jobId, ticket);
          link.style.display = "none";
          document.body.appendChild(link);
          link.click();
          link.remove();
        }
        if (nextJob.status === "complete") {
          setDownloading(false);
          toast.success("Folder download complete");
          return;
        }
        if (nextJob.status === "failed") {
          setDownloading(false);
          toast.error(nextJob.message || "Download failed");
          return;
        }
        downloadPollRef.current = setTimeout(check, 750);
      } catch (err) {
        setDownloading(false);
        toast.error(getErrorMessage(err, "Could not check download progress"));
      }
    };
    check();
  };

  const handleDownloadAll = async () => {
    if (!activeTab || downloading) return;
    if (downloadPollRef.current) clearTimeout(downloadPollRef.current);
    setDownloading(true);
    setDownloadJob({ status: "queued", files_done: 0, files_total: currentFiles.length, percent: 0, label: activeTab });
    downloadStartedRef.current = null;
    try {
      const response = await startAdminFolderDownload(id, activeTab);
      setDownloadJob(response.data);
      pollAdminDownload(response.data.id, response.data.ticket);
    } catch (err) {
      setDownloading(false);
      setDownloadJob(null);
      toast.error(getErrorMessage(err, "Download failed"));
    }
  };

  const handleDownloadSingleFile = async (file) => {
    try {
      const res = await adminDownloadFile(id, file.id);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = file.filename; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Download failed"); }
  };

  const handleCreateShare = async () => {
    setCreatingShare(true);
    try {
      const data = {
        gallery_id: id,
        subfolder: shareForm.subfolder || null,
        password: shareForm.password || null,
        access_level: shareForm.access_level,
        label: shareForm.label || null,
        expires_at: shareForm.expires_at || null,
        custom_slug: shareForm.custom_slug || null,
        guest_upload_mode: shareForm.guest_upload_mode,
        allow_all_file_types: shareForm.allow_all_file_types
      };
      await createShare(id, data);
      toast.success("Share link created");
      setShowShareDialog(false);
      setShareForm({ subfolder: null, password: "", access_level: "download", label: "", expires_at: null, custom_slug: "", guest_upload_mode: false });
      loadGallery();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally {
      setCreatingShare(false);
    }
  };

  const handleSetExpiry = async (shareId, date) => {
    try {
      const expiresAt = date ? date.toISOString() : null;
      await updateShareExpiry(shareId, expiresAt);
      toast.success(date ? "Expiry date set" : "Expiry removed");
      loadGallery();
    } catch (err) {
      toast.error("Failed to update expiry");
    }
  };

  const handleExpireNow = async (shareId) => {
    try {
      await toggleShare(shareId);
      toast.success("Share link expired");
      loadGallery();
    } catch (err) {
      toast.error("Failed to expire share");
    }
  };

  const formatExpiryDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  const isShareExpired = (share) => {
    if (!share.is_active) return true;
    if (!share.expires_at) return false;
    return new Date(share.expires_at) < new Date();
  };

  const handleDeleteShare = async (shareId) => {
    try {
      await deleteShare(shareId);
      toast.success("Share deleted");
      loadGallery();
    } catch { toast.error("Failed"); }
  };

  const copyShareLink = (token) => {
    navigator.clipboard.writeText(`${window.location.origin}/s/${token}`);
    toast.success("Share link copied");
  };

  const openEditShare = (share) => {
    setEditForm({ password: share.password_raw || '', label: share.label || '', access_level: share.access_level || 'download' });
    setEditingShare(share);
  };

  const handleSaveShare = async () => {
    try {
      const updates = {};
      if (editForm.label !== (editingShare.label || '')) updates.label = editForm.label;
      if (editForm.access_level !== (editingShare.access_level || 'download')) updates.access_level = editForm.access_level;
      if (editForm.password !== (editingShare.password_raw || '')) updates.password = editForm.password;
      if (Object.keys(updates).length === 0) { setEditingShare(null); return; }
      await updateShare(editingShare.id, updates);
      toast.success("Share updated");
      setEditingShare(null);
      loadGallery();
    } catch { toast.error("Failed to update share"); }
  };

  const toggleSelect = (fileId) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId); else next.add(fileId);
      return next;
    });
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--admin-bg)' }}>
      <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
    </div>
  );
  const handleReprocessVideos = async () => {
    try {
      setReprocessing(true);
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/admin/galleries/${id}/reprocess-videos`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('admin_token')}` }
      });
      const data = await res.json();
      if (data.queued === 0) {
        toast.info('No video files to optimise');
        setReprocessing(false);
        return;
      }
      // Show progress bar immediately with correct total
      setReprocessProgress({ total: data.queued, done: 0, current_file: 'Starting...' });
      toast.success(`Optimising ${data.queued} video(s)...`);
      // Start per-file transcode polling
      startTranscodePolling();
      // Poll for bulk progress
      const poll = setInterval(async () => {
        try {
          const pr = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/admin/galleries/${id}/reprocess-progress`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('admin_token')}` }
          });
          const prog = await pr.json();
          if (!prog.active) {
            clearInterval(poll);
            setReprocessing(false);
            setReprocessProgress({ total: data.queued, done: data.queued, current_file: null });
            toast.success('All videos optimised for streaming!');
            loadVideoHealth(); // Refresh health badges
            setTimeout(() => setReprocessProgress(null), 3000);
          } else {
            setReprocessProgress(prog);
          }
        } catch { /* ignore poll errors */ }
      }, 1000);
    } catch (err) {
      toast.error('Failed to start video optimisation');
      setReprocessing(false);
      setReprocessProgress(null);
    }
  };

  const handleSaveEmail = async () => {
    try {
      await updateGallery(id, { client_email: clientEmail });
      setEditingEmail(false);
      toast.success("Couple's email saved");
    } catch { toast.error("Failed to save email"); }
  };

  const handleThemeChange = async (themeId) => {
    setGalleryTheme(themeId);
    try {
      await updateGallery(id, { theme: themeId });
      toast.success("Gallery theme updated");
    } catch { toast.error("Failed to update theme"); }
  };

  const handleAlbumModeChange = async (mode) => {
    if ((gallery.album_selection?.mode || 'off') === mode) return;
    setUpdatingAlbumPlan(true);
    try {
      const res = await updateAlbumSelection(id, mode);
      setGallery(prev => ({ ...prev, album_selection: res.data.album_selection }));
      toast.success(mode === 'off'
        ? 'Album choices hidden from the couple'
        : `${mode} photos plus a separate cover enabled`);
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to update album plan'));
    } finally {
      setUpdatingAlbumPlan(false);
    }
  };

  const handleReopenAlbum = async () => {
    setUpdatingAlbumPlan(true);
    try {
      const res = await reopenAlbumSelection(id);
      setGallery(prev => ({ ...prev, album_selection: res.data.album_selection }));
      toast.success('Album choices reopened without removing the couple’s selections');
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to reopen album choices'));
    } finally {
      setUpdatingAlbumPlan(false);
    }
  };

  const handleSendAlbumInvitation = async () => {
    setSendingAlbumInvitation(true);
    try {
      const res = await sendAlbumSelectionInvitation(id);
      toast.success(res.data.message);
      loadGallery();
    } catch (err) {
      toast.error(getErrorMessage(err, 'Failed to send album instructions'));
    } finally {
      setSendingAlbumInvitation(false);
    }
  };

  const handleNotifyCouple = async () => {
    setShowReadiness(true);
    setCheckingReadiness(true);
    setGalleryReadiness(null);
    try {
      const res = await getGalleryReadiness(id);
      setGalleryReadiness(res.data);
    } catch (err) {
      toast.error(getErrorMessage(err, "Gallery Ready check failed"));
      setShowReadiness(false);
    } finally {
      setCheckingReadiness(false);
    }
  };

  const handleConfirmNotification = async () => {
    if (!galleryReadiness?.ready) return;
    setSendingNotification(true);
    try {
      const res = await sendGalleryNotification(id);
      toast.success(res.data.message);
      setShowReadiness(false);
      loadGallery();
    } catch (err) {
      toast.error(getErrorMessage(err, "Failed to send notification"));
    } finally { setSendingNotification(false); }
  };

  const handleOpenSendEmail = async () => {
    if (!clientEmail) {
      setEditingEmail(true);
      toast.error("Add the couple's email first");
      return;
    }
    setShowSendEmail(true);
    setSelectedTemplateId("");
    try {
      const res = await getEmailTemplates();
      setEmailTemplates(res.data);
    } catch (e) { setEmailTemplates([]); }
  };

  const handleSendTemplateEmail = async () => {
    if (!selectedTemplateId) {
      toast.error("Select a template");
      return;
    }
    setSendingTemplate(true);
    try {
      if (galleryEmailAttachments.length > 0) {
        // Use the multipart endpoint with attachments
        const tmpl = emailTemplates.find(t => t.id === selectedTemplateId);
        const fd = new FormData();
        fd.append("subject", tmpl?.subject || "");
        fd.append("body", tmpl?.body || "");
        fd.append("template_id", selectedTemplateId);
        galleryEmailAttachments.forEach(f => fd.append("attachments", f));
        const res = await sendGalleryEmail(id, fd);
        toast.success(res.data.message);
      } else {
        const res = await sendTemplateEmail(id, selectedTemplateId);
        toast.success(res.data.message);
      }
      setShowSendEmail(false);
      setGalleryEmailAttachments([]);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send email");
    } finally { setSendingTemplate(false); }
  };

  const handleSendQrPicker = async () => {
    if (!gallery.client_email) {
      setEditingEmail(true);
      toast.error("Add the couple's email first");
      return;
    }
    setSendingQrPicker(true);
    try {
      const res = await sendQrPickerEmail(id);
      toast.success(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send QR picker email");
    } finally { setSendingQrPicker(false); }
  };

  if (!gallery) return null;

  const currentFiles = files.filter(f => f.subfolder === activeTab);
  const photoFiles = currentFiles.filter(f => f.file_type === 'photo');
  const videoFiles = currentFiles.filter(f => f.file_type === 'video');

  // Video health lookup for current folder
  const videoHealthMap = {};
  const folderHealth = { total: 0, optimised: 0 };
  if (videoHealth?.videos) {
    for (const v of videoHealth.videos) {
      videoHealthMap[v.id] = v;
      if (v.subfolder === activeTab) {
        folderHealth.total++;
        if (v.has_web_version) folderHealth.optimised++;
      }
    }
  }

  const albumSelection = gallery.album_selection || {
    mode: 'off', limit: 40, selected_file_ids: [], cover_file_id: null,
    cover_filename: null, locked: false, history: []
  };
  const albumSelectedCount = (albumSelection.selected_file_ids || []).length;
  const albumEnabled = albumSelection.mode === '40' || albumSelection.mode === '60';

  return (
    <div className="min-h-screen w-full min-w-0 overflow-x-hidden" data-admin-page style={{ backgroundColor: 'var(--admin-bg)' }}>
      {/* Header */}
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'var(--admin-header-bg)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-3 sm:px-6 py-3 sm:py-4 flex flex-col items-stretch gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3 sm:gap-4 min-w-0">
            <button data-testid="back-to-dashboard" onClick={() => navigate("/admin/dashboard")} className="text-[#57534E] hover:text-[#1C1917]" style={{ transition: 'color 0.2s ease' }}>
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="min-w-0 flex-1">
              <h1 className="text-xl font-medium truncate" style={{ fontFamily: 'Cormorant Garamond, serif' }}>{gallery.folder_name}</h1>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p className="text-xs" style={{ color: 'var(--admin-faint)', fontFamily: 'Manrope, sans-serif' }}>{gallery.subfolders.length} subfolders &middot; {files.length} files</p>
                {editingEmail ? (
                  <div className="flex items-center gap-1.5 ml-2">
                    <Input data-testid="edit-client-email" type="email" value={clientEmail}
                      onChange={e => setClientEmail(e.target.value)} placeholder="couple@email.com"
                      className="h-6 text-xs w-44 border-[#D4AF37] rounded-sm px-2" autoFocus
                      onKeyDown={e => { if (e.key === 'Enter') handleSaveEmail(); if (e.key === 'Escape') setEditingEmail(false); }} />
                    <button onClick={handleSaveEmail} className="text-green-600 hover:text-green-800"><Check className="w-3.5 h-3.5" /></button>
                    <button onClick={() => setEditingEmail(false)} className="text-gray-400 hover:text-gray-600"><X className="w-3.5 h-3.5" /></button>
                  </div>
                ) : (
                  <button onClick={() => setEditingEmail(true)} className="flex items-center gap-1 ml-2 text-xs hover:text-[#D4AF37] transition-colors"
                    style={{ color: clientEmail ? 'var(--admin-muted)' : 'var(--admin-faint)', fontFamily: 'Manrope, sans-serif' }} data-testid="client-email-display">
                    <Mail className="w-3 h-3" />
                    {clientEmail || "Add email"}
                    {gallery.notification_sent_at && <span className="text-[9px] ml-1 text-green-600 font-semibold">Sent</span>}
                  </button>
                )}
              </div>
            </div>
          </div>
          <div className="w-full min-w-0 overflow-x-auto lg:w-auto" data-testid="admin-gallery-mobile-toolbar">
          <div className="flex min-w-max items-center gap-2 pb-1 lg:pb-0">
            <AdminThemeToggle />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button data-testid="theme-picker-btn" variant="outline"
                  className="rounded-sm px-3 py-2 text-xs tracking-wider uppercase font-bold gap-2 border-[#57534E]/30 text-[#57534E] hover:bg-[#57534E]/5">
                  <Palette className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">{THEME_LIST.find(th => th.id === galleryTheme)?.name || 'Theme'}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 p-2">
                {THEME_LIST.map(th => (
                  <DropdownMenuItem key={th.id} data-testid={`theme-${th.id}`}
                    onClick={() => handleThemeChange(th.id)}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-sm cursor-pointer ${galleryTheme === th.id ? 'bg-stone-100' : ''}`}>
                    <div className="flex gap-0.5">
                      <div className="w-4 h-4 rounded-full border border-gray-200" style={{ backgroundColor: th.preview.bg }} />
                      <div className="w-4 h-4 rounded-full border border-gray-200" style={{ backgroundColor: th.preview.accent }} />
                      <div className="w-4 h-4 rounded-full border border-gray-200" style={{ backgroundColor: th.preview.text }} />
                    </div>
                    <span className="text-xs font-medium" style={{ fontFamily: 'Manrope, sans-serif' }}>{th.name}</span>
                    {galleryTheme === th.id && <Check className="w-3.5 h-3.5 ml-auto text-green-600" />}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button data-testid="notify-couple-btn" onClick={handleNotifyCouple} disabled={sendingNotification || checkingReadiness}
              variant="outline" className="rounded-sm px-4 py-2 text-xs tracking-wider uppercase font-bold gap-2 border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37]/10">
              <Mail className="w-3.5 h-3.5" /> {checkingReadiness ? "Checking..." : sendingNotification ? "Sending..." : "Notify Couple"}
            </Button>
            <Button data-testid="send-template-email-btn" onClick={handleOpenSendEmail}
              variant="outline" className="rounded-sm px-4 py-2 text-xs tracking-wider uppercase font-bold gap-2 border-[#57534E] text-[#57534E] hover:bg-[#57534E]/10">
              <Send className="w-3.5 h-3.5" /> Send Email
            </Button>
            <Button data-testid="send-qr-picker-btn" onClick={handleSendQrPicker} disabled={sendingQrPicker}
              variant="outline" className="rounded-sm px-4 py-2 text-xs tracking-wider uppercase font-bold gap-2 border-[#D4AF37] text-[#D4AF37] hover:bg-[#D4AF37]/10">
              <QrCode className="w-3.5 h-3.5" /> {sendingQrPicker ? "Sending..." : "QR Picker"}
            </Button>
            <Button data-testid="create-share-btn" onClick={() => setShowShareDialog(true)}
              className="bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-5 py-2 text-xs tracking-wider uppercase font-bold gap-2">
              <Share2 className="w-3.5 h-3.5" /> Create Share
            </Button>
          </div>
          </div>
        </div>
      </header>

      <main className="w-full min-w-0 max-w-screen-xl mx-auto px-3 sm:px-6 py-4 sm:py-6">
        {/* Album package and couple-selection controls */}
        <section data-testid="album-selection-admin-card" className="mb-6 border p-3 sm:p-5" style={{ borderColor: 'var(--admin-border)', backgroundColor: 'var(--admin-surface)' }}>
          <div className="flex flex-col lg:flex-row lg:items-start gap-5">
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <BookOpen className="w-4 h-4 text-[#D4AF37]" />
                <h2 className="text-sm tracking-wider uppercase font-bold" style={{ fontFamily: 'Manrope, sans-serif', color: 'var(--admin-text)' }}>Wedding Album Choices</h2>
                <span className={`text-[10px] px-2 py-0.5 font-bold uppercase ${albumSelection.locked ? 'bg-green-100 text-green-700' : albumEnabled ? 'bg-amber-100 text-amber-700' : 'bg-stone-100 text-stone-500'}`}>
                  {albumSelection.locked ? 'Submitted & Locked' : albumEnabled ? 'Open' : 'Off'}
                </span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
                Off hides every album instruction and control from the couple. Turning it on keeps the existing gallery link and defaults to the 40-photo package.
              </p>

              {albumEnabled && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
                  <div className="p-3 border" style={{ borderColor: 'var(--admin-border)', backgroundColor: 'var(--admin-surface-soft)' }}>
                    <p className="text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--admin-faint)' }}>Album photos</p>
                    <p className="text-xl font-semibold mt-1" style={{ color: 'var(--admin-text)' }}>{albumSelectedCount} <span className="text-sm font-normal" style={{ color: 'var(--admin-muted)' }}>/ {albumSelection.limit}</span></p>
                  </div>
                  <div className="p-3 border" style={{ borderColor: 'var(--admin-border)', backgroundColor: 'var(--admin-surface-soft)' }}>
                    <p className="text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--admin-faint)' }}>Separate cover</p>
                    <p className="text-xs font-semibold mt-2 truncate" style={{ color: albumSelection.cover_file_id ? '#16A34A' : 'var(--admin-muted)' }} title={albumSelection.cover_filename || ''}>
                      {albumSelection.cover_filename || 'Not chosen yet'}
                    </p>
                  </div>
                  <div className="p-3 border" style={{ borderColor: 'var(--admin-border)', backgroundColor: 'var(--admin-surface-soft)' }}>
                    <p className="text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--admin-faint)' }}>Last submission</p>
                    <p className="text-xs font-semibold mt-2" style={{ color: 'var(--admin-text)' }}>
                      {albumSelection.submitted_at
                        ? new Date(albumSelection.submitted_at).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
                        : 'Not submitted'}
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="lg:w-[420px] space-y-3">
              <div className="grid grid-cols-3 border" style={{ borderColor: 'var(--admin-border)' }}>
                {[
                  { mode: 'off', label: 'Off' },
                  { mode: '40', label: '40 + Cover' },
                  { mode: '60', label: '60 + Cover' },
                ].map(option => (
                  <button key={option.mode} data-testid={`album-mode-${option.mode}`}
                    onClick={() => handleAlbumModeChange(option.mode)} disabled={updatingAlbumPlan}
                    className="px-3 py-2.5 text-xs font-bold transition-colors disabled:opacity-50"
                    style={{
                      fontFamily: 'Manrope, sans-serif',
                      backgroundColor: albumSelection.mode === option.mode ? '#D4AF37' : 'var(--admin-surface-raised)',
                      color: albumSelection.mode === option.mode ? '#FFFFFF' : 'var(--admin-muted)',
                    }}>
                    {option.label}
                  </button>
                ))}
              </div>

              {albumEnabled && (
                <div className="flex flex-wrap gap-2">
                  <Button data-testid="send-album-instructions-btn" variant="outline" onClick={handleSendAlbumInvitation} disabled={sendingAlbumInvitation || !clientEmail}
                    className="rounded-sm text-xs gap-1.5 border-[#D4AF37] text-[#B08D24]">
                    <Mail className="w-3.5 h-3.5" /> {sendingAlbumInvitation ? 'Sending...' : 'Email Album Instructions'}
                  </Button>
                  {albumSelection.locked && (
                    <Button data-testid="reopen-album-choices-btn" variant="outline" onClick={handleReopenAlbum} disabled={updatingAlbumPlan}
                      className="rounded-sm text-xs gap-1.5">
                      <Unlock className="w-3.5 h-3.5" /> Reopen Choices
                    </Button>
                  )}
                </div>
              )}

              {(albumSelection.history || []).length > 0 && (
                <details className="text-xs" style={{ color: 'var(--admin-muted)' }}>
                  <summary className="cursor-pointer flex items-center gap-1.5 font-semibold"><History className="w-3.5 h-3.5" /> Selection history</summary>
                  <div className="mt-2 space-y-1 max-h-28 overflow-y-auto">
                    {[...(albumSelection.history || [])].reverse().slice(0, 8).map((item, index) => (
                      <p key={`${item.at}-${index}`} className="flex justify-between gap-3">
                        <span>{item.action.replaceAll('_', ' ')}</span>
                        <span className="whitespace-nowrap">{new Date(item.at).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })}</span>
                      </p>
                    ))}
                  </div>
                </details>
              )}
            </div>
          </div>
        </section>

        {/* Shares Bar */}
        {shares.length > 0 && (
          <div className="mb-6 p-4 border" style={{ borderColor: 'var(--admin-border)' }}>
            <div className="flex items-center gap-2 mb-3">
              <Share2 className="w-4 h-4 text-[#D4AF37]" />
              <span className="text-xs tracking-wider uppercase font-bold" style={{ fontFamily: 'Manrope, sans-serif' }}>Active Shares ({shares.length})</span>
            </div>
            <div className="space-y-2">
              {shares.map(s => (
                <div key={s.id} className={`flex flex-wrap items-center gap-2 sm:gap-3 p-2 text-sm ${isShareExpired(s) ? 'opacity-50' : ''}`} style={{ backgroundColor: s.is_active && !isShareExpired(s) ? 'var(--admin-surface-raised)' : 'var(--admin-surface-soft)' }}>
                  <div className="w-full sm:flex-1 flex items-center gap-2 flex-wrap min-w-0" style={{ fontFamily: 'Manrope, sans-serif' }}>
                    {s.has_password ? <Lock className="w-3.5 h-3.5 text-[#57534E]" /> : <Globe className="w-3.5 h-3.5 text-[#3F6212]" />}
                    <span className="text-xs font-medium">{s.label}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-[#D4AF37]/10 text-[#D4AF37] font-bold uppercase">
                      {s.access_level === 'view' ? 'VIEW ONLY' : 
                       s.access_level === 'download' ? 'DOWNLOAD' :
                       s.access_level === 'upload' ? 'UPLOAD' : 'FULL ACCESS'}
                    </span>
                    {s.guest_upload_mode && (
                      <span className="text-xs px-1.5 py-0.5 bg-[#0891B2]/10 text-[#0891B2] font-bold uppercase flex items-center gap-1">
                        <Upload className="w-3 h-3" /> GUEST MODE
                      </span>
                    )}
                    {s.allow_all_file_types && (
                      <span className="text-xs px-1.5 py-0.5 bg-[#7C3AED]/10 text-[#7C3AED] font-bold uppercase flex items-center gap-1">
                        ALL FILES
                      </span>
                    )}
                    {s.subfolder && <span className="text-xs px-1.5 py-0.5 bg-[#78716C]/10 text-[#78716C]">{s.subfolder}</span>}
                    {s.expires_at && (
                      <span className={`text-xs px-1.5 py-0.5 flex items-center gap-1 ${isShareExpired(s) ? 'bg-[#9F1239]/10 text-[#9F1239]' : 'bg-[#78716C]/10 text-[#78716C]'}`}>
                        <Clock className="w-3 h-3" />
                        {isShareExpired(s) ? 'Expired' : `Expires ${formatExpiryDate(s.expires_at)}`}
                      </span>
                    )}
                    {!s.is_active && <span className="text-xs text-[#9F1239] font-bold">DISABLED</span>}
                  </div>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button className="p-1 text-[#57534E] hover:text-[#1C1917]" title="Set expiry date">
                        <CalendarIcon className="w-3.5 h-3.5" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="end">
                      <div className="p-2 border-b">
                        <p className="text-xs font-medium text-[#57534E]">Set expiry date</p>
                      </div>
                      <Calendar
                        mode="single"
                        selected={s.expires_at ? new Date(s.expires_at) : undefined}
                        onSelect={(date) => handleSetExpiry(s.id, date)}
                        disabled={(date) => date < new Date()}
                        initialFocus
                      />
                      {s.expires_at && (
                        <div className="p-2 border-t">
                          <Button variant="ghost" size="sm" className="w-full text-xs" onClick={() => handleSetExpiry(s.id, null)}>
                            Remove expiry
                          </Button>
                        </div>
                      )}
                    </PopoverContent>
                  </Popover>
                  <button data-testid={`edit-share-${s.id}`} onClick={() => openEditShare(s)} className="p-1 text-[#57534E] hover:text-[#1C1917]" title="Edit share"><Pencil className="w-3.5 h-3.5" /></button>
                  <button data-testid={`copy-share-${s.id}`} onClick={() => copyShareLink(s.token)} className="p-1 text-[#57534E] hover:text-[#1C1917]"><Copy className="w-3.5 h-3.5" /></button>
                  <button data-testid={`qr-share-${s.id}`} onClick={() => setShowQR(s)} className="p-1 text-[#57534E] hover:text-[#1C1917]"><QrCode className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleExpireNow(s.id)} className="p-1 text-[#57534E] hover:text-[#1C1917]" title={s.is_active ? "Disable share" : "Enable share"}>
                    {s.is_active ? <Globe className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
                  </button>
                  <button onClick={() => handleDeleteShare(s.id)} className="p-1 text-[#9F1239]"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Subfolder Tabs */}
        <Tabs value={activeTab} onValueChange={v => { setActiveTab(v); setSelectedFiles(new Set()); }}>
          <div className="flex items-center gap-1 border-b mb-6 min-w-0" style={{ borderColor: 'var(--admin-border)' }}>
            <TabsList className="bg-transparent flex-1 min-w-0 justify-start rounded-none h-auto p-0 overflow-x-auto">
              {gallery.subfolders.map(sf => {
                const count = (gallery.file_counts || {})[sf] || 0;
                return (
                  <TabsTrigger key={sf} value={sf} data-testid={`tab-${sf.replace(/\s/g, '-')}`}
                    className="rounded-none border-b-2 border-transparent data-[state=active]:border-[#D4AF37] data-[state=active]:text-[#1C1917] data-[state=active]:shadow-none px-4 py-3 text-xs tracking-wider uppercase font-semibold text-[#A8A29E]"
                    style={{ fontFamily: 'Manrope, sans-serif' }}>
                    {sf} <span className="ml-1.5 text-[10px] opacity-60">({count})</span>
                  </TabsTrigger>
                );
              })}
            </TabsList>
            <Button
              data-testid="add-subfolder-btn"
              variant="ghost"
              onClick={() => { setNewFolderName(""); setShowAddFolderDialog(true); }}
              className="shrink-0 text-[#3F6212] hover:text-[#365314] hover:bg-[#3F6212]/5 rounded-sm px-2 sm:px-3 py-2 text-xs gap-1.5"
              style={{ fontFamily: 'Manrope, sans-serif' }}
              title="Add folder"
            >
              <Plus className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Add Folder</span>
            </Button>
            {activeTab && (
              <Button
                data-testid={`delete-subfolder-btn`}
                variant="ghost"
                onClick={() => handleDeleteSubfolder(activeTab)}
                className="ml-auto shrink-0 text-[#9F1239]/60 hover:text-[#9F1239] hover:bg-[#9F1239]/5 rounded-sm px-3 py-2 text-xs gap-1.5"
                style={{ fontFamily: 'Manrope, sans-serif' }}
              >
                <Trash2 className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Remove Folder</span>
              </Button>
            )}
          </div>

          {gallery.subfolders.map(sf => (
            <TabsContent key={sf} value={sf} className="mt-0">
              {/* Upload Zone */}
              <div
                className={`upload-zone mb-4 p-6 flex flex-col items-center justify-center text-center cursor-pointer ${dragOver ? 'drag-over' : ''}`}
                style={{ minHeight: '100px' }}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                data-testid={`upload-zone-${sf.replace(/\s/g, '-')}`}
              >
                <input ref={fileInputRef} type="file" multiple accept="image/*,video/*" className="hidden"
                  onChange={e => handleUpload(e.target.files)} data-testid="file-input" />
                {uploading ? (
                  <div className="w-full max-w-xs">
                    <p className="text-sm mb-2" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>Uploading to {sf}... {uploadProgress}%</p>
                    <Progress value={uploadProgress} className="h-1.5" />
                  </div>
                ) : (
                  <>
                    <Upload className="w-6 h-6 mb-2 text-[#A8A29E]" strokeWidth={1.5} />
                    <p className="text-sm" style={{ fontFamily: 'Manrope, sans-serif', color: 'var(--admin-muted)' }}>Drop files here or click to upload to <strong>{sf}</strong></p>
                    <p className="text-xs mt-1" style={{ color: 'var(--admin-faint)' }}>Original filenames preserved. No size limit.</p>
                  </>
                )}
              </div>

              {/* Action Bar */}
              {currentFiles.length > 0 && (
                <>
                <div className="flex items-center gap-2 mb-4 flex-wrap">
                  <Button data-testid="select-mode-btn" variant={selectMode ? "default" : "outline"} 
                    onClick={() => { setSelectMode(m => !m); setSelectedFiles(new Set()); }}
                    className={`rounded-sm text-xs tracking-wider gap-1.5 ${selectMode ? 'bg-[#1C1917] text-[#FDFCF8]' : 'border-[#D4D4D8] text-[#57534E]'}`}
                    style={{ fontFamily: 'Manrope, sans-serif' }}>
                    <Check className="w-3.5 h-3.5" /> {selectMode ? "Cancel Select" : "Select"}
                  </Button>

                  {selectMode && (
                    <>
                      <Button data-testid="select-all-btn" variant="outline"
                        onClick={() => {
                          if (selectedFiles.size === currentFiles.length) {
                            setSelectedFiles(new Set());
                          } else {
                            setSelectedFiles(new Set(currentFiles.map(f => f.id)));
                          }
                        }}
                        className="rounded-sm text-xs tracking-wider gap-1.5 border-[#D4D4D8] text-[#57534E]"
                        style={{ fontFamily: 'Manrope, sans-serif' }}>
                        {selectedFiles.size === currentFiles.length ? "Deselect All" : "Select All"}
                      </Button>
                      {selectedFiles.size > 0 && (
                        <>
                          <span className="text-xs font-bold" style={{ fontFamily: 'Manrope, sans-serif', color: 'var(--admin-muted)' }}>{selectedFiles.size} selected</span>
                          {gallery.subfolders.includes("Album Favourites") && activeTab !== "Album Favourites" && (
                            <Button data-testid="copy-to-favourites-btn" onClick={handleCopyToFavourites} disabled={copying}
                              className="bg-[#D4AF37] text-white hover:bg-[#D4AF37]/90 rounded-sm text-xs tracking-wider gap-1.5 font-bold"
                              style={{ fontFamily: 'Manrope, sans-serif' }}>
                              <Heart className="w-3.5 h-3.5" /> {copying ? "Copying..." : "Add to Album Favourites"}
                            </Button>
                          )}
                          <Button data-testid="bulk-delete-btn" onClick={handleBulkDelete} variant="ghost" className="text-[#9F1239] text-xs gap-1">
                            <Trash2 className="w-3.5 h-3.5" /> Delete
                          </Button>
                        </>
                      )}
                    </>
                  )}

                  <div className="w-full sm:w-auto sm:ml-auto flex flex-wrap items-center gap-2">
                    {/* Video health summary */}
                    {videoFiles.length > 0 && folderHealth.total > 0 && !reprocessProgress && !Object.keys(transcodeStatus).length && (
                      <div data-testid="video-health-summary" className="flex items-center gap-2 px-3 py-1.5 rounded-sm border"
                        style={{ 
                          borderColor: folderHealth.optimised === folderHealth.total ? '#4ADE80' : '#F59E0B',
                          backgroundColor: folderHealth.optimised === folderHealth.total ? '#F0FDF4' : '#FFFBEB'
                        }}>
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: folderHealth.optimised === folderHealth.total ? '#16A34A' : '#F59E0B' }} />
                        <span className="text-[10px] font-medium" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
                          {folderHealth.optimised}/{folderHealth.total} web-optimised
                        </span>
                        {folderHealth.optimised < folderHealth.total && (
                          <span className="text-[10px]" style={{ color: '#D97706', fontFamily: 'Manrope, sans-serif' }}>
                            {folderHealth.total - folderHealth.optimised} pending
                          </span>
                        )}
                      </div>
                    )}
                    {videoFiles.length > 0 && !reprocessProgress && (
                      <Button data-testid="optimise-videos-btn" variant="outline" onClick={handleReprocessVideos} disabled={reprocessing}
                        className="rounded-sm text-xs tracking-wider gap-1.5 border-[#D4D4D8] text-[#57534E]"
                        style={{ fontFamily: 'Manrope, sans-serif' }}>
                        <Film className="w-3.5 h-3.5" /> {reprocessing ? "Starting..." : "Optimise Videos for Web"}
                      </Button>
                    )}
                    {reprocessProgress && reprocessProgress.total > 0 && (
                      <div className="w-full sm:w-auto sm:min-w-[240px] flex items-center gap-3 px-3 py-1.5 rounded-sm border" style={{ borderColor: '#D4AF37', backgroundColor: '#FEFCE8' }}>
                        <Film className="w-3.5 h-3.5 shrink-0" style={{ color: '#D4AF37' }} />
                        <div className="flex-1">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] font-medium" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
                              {reprocessProgress.done >= reprocessProgress.total ? 'Done!' : reprocessProgress.current_file || 'Processing...'}
                            </span>
                            <span className="text-[10px] font-bold" style={{ color: '#D4AF37', fontFamily: 'Manrope, sans-serif' }}>
                              {reprocessProgress.done}/{reprocessProgress.total}
                            </span>
                          </div>
                          <Progress value={reprocessProgress.total > 0 ? (reprocessProgress.done / reprocessProgress.total) * 100 : 0} className="h-1.5" />
                        </div>
                      </div>
                    )}
                    {/* Auto-transcode indicator (shows when videos are transcoding after upload, not from Optimise button) */}
                    {!reprocessProgress && Object.keys(transcodeStatus).length > 0 && (
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-sm border" style={{ borderColor: '#D4AF37', backgroundColor: '#FEFCE8' }}>
                        <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: '#D4AF37' }} />
                        <span className="text-[10px] font-medium" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
                          Transcoding {Object.values(transcodeStatus).filter(t => t.status === 'transcoding').length} video(s)...
                        </span>
                        {Object.values(transcodeStatus).filter(t => t.status === 'transcoding').map((t) => (
                          <span key={t.filename} className="text-[10px] font-bold" style={{ color: '#D4AF37', fontFamily: 'Manrope, sans-serif' }}>
                            {t.method} {t.percent}%
                          </span>
                        ))}
                      </div>
                    )}
                    <Button data-testid="download-all-btn" variant="outline" onClick={handleDownloadAll} disabled={downloading}
                      className="rounded-sm text-xs tracking-wider gap-1.5 border-[#D4D4D8] text-[#57534E]"
                      style={{ fontFamily: 'Manrope, sans-serif' }}>
                      <Download className="w-3.5 h-3.5" /> {downloading ? "Preparing…" : `Download All (${currentFiles.length})`}
                    </Button>
                  </div>
                </div>
                {downloadJob?.label === activeTab && (
                  <div className="mb-4 ml-auto w-full sm:max-w-md">
                    <DownloadJobProgress job={downloadJob} />
                  </div>
                )}
                </>
              )}

              {/* Files Grid */}
              {currentFiles.length === 0 ? (
                <div className="text-center py-16">
                  <FolderOpen className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" strokeWidth={1} />
                  <p className="text-lg" style={{ fontFamily: 'Cormorant Garamond, serif', color: 'var(--admin-muted)' }}>No files in {sf}</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                  {currentFiles.map((file, i) => {
                    const isCover = gallery.covers && gallery.covers[activeTab] === file.id;
                    const tc = transcodeStatus[file.id];
                    const isTranscoding = tc && tc.status === 'transcoding';
                    const justCompleted = tc && tc.status === 'complete';
                    const vh = file.file_type === 'video' ? videoHealthMap[file.id] : null;
                    return (
                    <motion.div key={file.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: Math.min(i * 0.01, 0.5) }}
                      className={`photo-card relative group aspect-square ${selectMode ? 'cursor-pointer' : ''} ${selectedFiles.has(file.id) ? 'ring-2 ring-[#D4AF37]' : ''} ${isCover ? 'ring-2 ring-amber-400' : ''}`}
                      data-testid={`file-${file.id}`}
                      onClick={selectMode ? () => toggleSelect(file.id) : undefined}>
                      {file.file_type === 'photo' && file.has_thumb ? (
                        <img src={thumbUrl(gallery.id, file.subfolder, file.filename)} alt={file.filename}
                          className="w-full h-full object-cover" loading="lazy" />
                      ) : file.file_type === 'video' ? (
                        file.has_thumb ? (
                          <div className="relative w-full h-full">
                            <img src={thumbUrl(gallery.id, file.subfolder, file.filename)} alt={file.filename}
                              className="w-full h-full object-cover" loading="lazy" />
                            <div className="absolute inset-0 flex items-center justify-center">
                              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.45)' }}>
                                <Film className="w-4 h-4 text-white" />
                              </div>
                            </div>
                            <span className="absolute bottom-1 left-1 text-[10px] px-1.5 py-0.5 rounded truncate max-w-[90%]" style={{ backgroundColor: 'rgba(0,0,0,0.6)', color: 'white' }}>{file.filename}</span>
                          </div>
                        ) : (
                          <div className="w-full h-full flex flex-col items-center justify-center" style={{ backgroundColor: 'var(--admin-surface-raised)' }}>
                            <Film className="w-8 h-8 text-[#A8A29E] mb-1" />
                            <span className="text-xs text-[#A8A29E] truncate max-w-[80%]">{file.filename}</span>
                          </div>
                        )
                      ) : file.file_type === 'audio' ? (
                        <SecureAudioPlayer file={file}
                          fetchAudio={() => adminDownloadFile(gallery.id, file.id)}
                          onDownload={handleDownloadSingleFile} compact />
                      ) : (
                        <div className="w-full h-full flex flex-col items-center justify-center" style={{ backgroundColor: 'var(--admin-surface-raised)' }}>
                          <FileText className="w-8 h-8 text-[#A8A29E] mb-1" />
                          <span className="text-xs text-[#A8A29E] truncate max-w-[80%]">{file.filename}</span>
                          <span className="text-[10px] text-[#C4C0B8] mt-0.5">{(file.file_size / (1024*1024)).toFixed(1)} MB</span>
                        </div>
                      )}
                      {/* Transcode progress overlay */}
                      {(isTranscoding || justCompleted) && (
                        <div className="absolute inset-x-0 bottom-0 z-10" data-testid={`transcode-progress-${file.id}`}>
                          <div className="px-2 py-1.5" style={{ background: 'linear-gradient(transparent, rgba(0,0,0,0.85))' }}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-[9px] font-semibold tracking-wider uppercase" style={{ color: justCompleted ? '#4ADE80' : '#D4AF37', fontFamily: 'Manrope, sans-serif' }}>
                                {justCompleted ? 'Ready' : `${tc.method} ${tc.percent}%`}
                              </span>
                              {isTranscoding && (
                                <span className="text-[9px]" style={{ color: 'rgba(255,255,255,0.7)', fontFamily: 'Manrope, sans-serif' }}>
                                  Optimising
                                </span>
                              )}
                            </div>
                            <div className="w-full h-1 rounded-full overflow-hidden" style={{ backgroundColor: 'rgba(255,255,255,0.2)' }}>
                              <div className="h-full rounded-full transition-all duration-700 ease-out"
                                style={{ 
                                  width: `${tc.percent}%`, 
                                  backgroundColor: justCompleted ? '#4ADE80' : '#D4AF37'
                                }} />
                            </div>
                          </div>
                        </div>
                      )}
                      {/* Cover indicator */}
                      {isCover && (
                        <div className="absolute top-2 right-2 px-2 py-1 rounded-full flex items-center gap-1 text-xs font-medium" 
                          style={{ backgroundColor: '#D4AF37', color: 'white' }}>
                          <Star className="w-3 h-3" fill="white" /> Cover
                        </div>
                      )}
                      {/* Video web-optimised health badge */}
                      {vh && !isCover && !isTranscoding && !justCompleted && (
                        <div data-testid={`video-health-${file.id}`} className="absolute top-2 right-2 px-1.5 py-0.5 rounded flex items-center gap-1"
                          style={{ backgroundColor: vh.has_web_version ? 'rgba(22,163,74,0.85)' : 'rgba(217,119,6,0.85)' }}
                          title={vh.has_web_version 
                            ? `Web-optimised: ${vh.web_mb}MB (original ${vh.original_mb}MB)` 
                            : `Not optimised — streaming original ${vh.original_mb}MB`}>
                          {vh.has_web_version 
                            ? <Check className="w-3 h-3 text-white" />
                            : <RefreshCw className="w-3 h-3 text-white" />}
                          <span className="text-[9px] font-semibold text-white" style={{ fontFamily: 'Manrope, sans-serif' }}>
                            {vh.has_web_version ? `${vh.web_mb}MB` : 'Not optimised'}
                          </span>
                        </div>
                      )}
                      {/* Selection checkbox - always visible in select mode */}
                      {selectMode && (
                        <div className="absolute top-2 left-2 w-6 h-6 rounded-sm border flex items-center justify-center"
                          style={{ backgroundColor: selectedFiles.has(file.id) ? '#D4AF37' : 'rgba(255,255,255,0.9)', borderColor: selectedFiles.has(file.id) ? '#D4AF37' : '#D4D4D8' }}>
                          {selectedFiles.has(file.id) && <Check className="w-3.5 h-3.5 text-white" />}
                        </div>
                      )}
                      {/* Hover overlay (non-select mode) */}
                      {!selectMode && file.file_type !== 'audio' && (
                        <>
                          <div className="photo-overlay" />
                          <div className="photo-actions flex items-center justify-between">
                            <div className="flex items-center gap-1">
                              {file.file_type === 'photo' && !isCover && (
                                <button data-testid={`set-cover-${file.id}`} onClick={async () => {
                                    try {
                                      await setSubfolderCover(gallery.id, activeTab, file.id);
                                      toast.success('Cover image set');
                                      loadGallery();
                                    } catch { toast.error('Failed to set cover'); }
                                  }}
                                  className="w-7 h-7 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
                                  title="Set as Cover">
                                  <Star className="w-3.5 h-3.5 text-amber-500" />
                                </button>
                              )}
                              {(file.file_type === 'video' || file.file_type === 'other') && (
                                <button data-testid={`download-file-${file.id}`} onClick={() => handleDownloadSingleFile(file)}
                                  className="w-7 h-7 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}
                                  title="Download">
                                  <Download className="w-3.5 h-3.5 text-[#1C1917]" />
                                </button>
                              )}
                            </div>
                            <button data-testid={`delete-file-${file.id}`} onClick={() => handleDeleteFile(file.id)}
                              className="w-7 h-7 rounded-full flex items-center justify-center" style={{ backgroundColor: 'rgba(255,255,255,0.9)' }}>
                              <Trash2 className="w-3.5 h-3.5 text-[#9F1239]" />
                            </button>
                          </div>
                        </>
                      )}
                    </motion.div>
                  )})}
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>
      </main>

      {/* Create Share Dialog */}
      <Dialog open={showShareDialog} onOpenChange={setShowShareDialog}>
        <DialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none max-w-lg" style={{ backgroundColor: 'var(--admin-bg)' }}>
          <DialogHeader>
            <DialogTitle className="text-3xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Create Share Link</DialogTitle>
            <DialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
              Share this gallery or a specific subfolder with a couple or their guests
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-5 mt-2">
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>What to share</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <button data-testid="share-whole-gallery" onClick={() => setShareForm(f => ({...f, subfolder: null}))}
                  className={`p-3 border text-left text-xs ${!shareForm.subfolder ? 'border-[#D4AF37] bg-[#D4AF37]/5' : 'border-[#F5F2EB]'}`}
                  style={{ fontFamily: 'Manrope, sans-serif' }}>
                  <FolderOpen className="w-4 h-4 mb-1 text-[#D4AF37]" />
                  <span className="block font-bold">Entire Gallery</span>
                  <span className="text-[#A8A29E]">All subfolders</span>
                </button>
                {gallery.subfolders.map(sf => (
                  <button key={sf} data-testid={`share-subfolder-${sf.replace(/\s/g, '-')}`}
                    onClick={() => setShareForm(f => ({...f, subfolder: sf}))}
                    className={`p-3 border text-left text-xs ${shareForm.subfolder === sf ? 'border-[#D4AF37] bg-[#D4AF37]/5' : 'border-[#F5F2EB]'}`}
                    style={{ fontFamily: 'Manrope, sans-serif' }}>
                    <FolderOpen className="w-4 h-4 mb-1 text-[#78716C]" />
                    <span className="block font-bold">{sf}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Label (optional)</Label>
              <Input data-testid="share-label-input" value={shareForm.label} onChange={e => setShareForm(f => ({...f, label: e.target.value}))}
                placeholder="e.g. Gina & Mark's Gallery" className="border-[#D4D4D8] rounded-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Custom URL (optional)</Label>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <span className="text-xs text-[#A8A29E] break-all">{window.location.origin}/</span>
                <Input data-testid="share-custom-slug-input" value={shareForm.custom_slug} 
                  onChange={e => setShareForm(f => ({...f, custom_slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '')}))}
                  placeholder="ginamark301122" className="border-[#D4D4D8] rounded-sm flex-1" />
              </div>
              <p className="text-xs text-[#A8A29E]">Leave empty for auto-generated URL. Only letters, numbers and hyphens allowed.</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Password (leave empty for no password)</Label>
              <div className="flex flex-col sm:flex-row gap-2">
                <Input data-testid="share-password-input" name="new-share-password" autoComplete="new-password" data-lpignore="true"
                  value={shareForm.password} onChange={e => setShareForm(f => ({...f, password: e.target.value}))}
                  placeholder="Optional - leave blank for open access" className="border-[#D4D4D8] rounded-sm flex-1" />
                <Button type="button" variant="outline" size="sm" data-testid="generate-password-btn"
                  className="shrink-0 text-xs gap-1.5 border-[#D4D4D8] hover:bg-[#F5F2EB]"
                  onClick={() => {
                    const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
                    let pw = '';
                    for (let i = 0; i < 8; i++) pw += chars[Math.floor(Math.random() * chars.length)];
                    setShareForm(f => ({...f, password: pw}));
                  }}>
                  <RefreshCw className="w-3.5 h-3.5" /> Generate
                </Button>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Access Level</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {[
                  { value: 'view', label: 'View Only', desc: 'Can only view photos' },
                  { value: 'download', label: 'View & Download', desc: 'Can view and download' },
                  { value: 'upload', label: 'View, Download & Upload', desc: 'Can also upload files' },
                  { value: 'full', label: 'Full Access', desc: 'Can view, download, upload & delete' }
                ].map(level => (
                  <button key={level.value} data-testid={`access-level-${level.value}`}
                    onClick={() => setShareForm(f => ({...f, access_level: level.value}))}
                    className={`p-3 border text-left text-xs ${shareForm.access_level === level.value ? 'border-[#D4AF37] bg-[#D4AF37]/5' : 'border-[#F5F2EB]'}`}
                    style={{ fontFamily: 'Manrope, sans-serif' }}>
                    <span className="block font-bold">{level.label}</span>
                    <span className="text-[#A8A29E]">{level.desc}</span>
                  </button>
                ))}
              </div>
            </div>
            {/* Guest Upload Mode - Only show when upload is enabled */}
            {(shareForm.access_level === 'upload' || shareForm.access_level === 'full') && (
              <div className="p-4 border rounded-sm" style={{ borderColor: '#D4AF37', backgroundColor: 'rgba(212,175,55,0.05)' }}>
                <label className="flex items-start gap-3 cursor-pointer" data-testid="guest-upload-mode-toggle">
                  <input
                    type="checkbox"
                    checked={shareForm.guest_upload_mode}
                    onChange={(e) => setShareForm(f => ({...f, guest_upload_mode: e.target.checked}))}
                    className="mt-1 w-4 h-4 rounded border-[#D4AF37] text-[#D4AF37] focus:ring-[#D4AF37]"
                  />
                  <div>
                    <span className="block font-bold text-sm" style={{ fontFamily: 'Manrope, sans-serif', color: 'var(--admin-text)' }}>
                      Guest Upload Mode
                    </span>
                    <span className="text-xs" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
                      Shows a simplified upload-only screen for wedding guests. No album browsing, no downloads - just a big upload button and a live counter.
                    </span>
                  </div>
                </label>
              </div>
            )}
            {/* Photographer Upload - Allow all file types */}
            {(shareForm.access_level === 'upload' || shareForm.access_level === 'full') && (
              <div className="p-4 border rounded-sm" style={{ borderColor: '#8B6914', backgroundColor: 'rgba(139,105,20,0.05)' }}>
                <label className="flex items-start gap-3 cursor-pointer" data-testid="allow-all-file-types-toggle">
                  <input
                    type="checkbox"
                    checked={shareForm.allow_all_file_types}
                    onChange={(e) => setShareForm(f => ({...f, allow_all_file_types: e.target.checked}))}
                    className="mt-1 w-4 h-4 rounded border-[#8B6914] text-[#8B6914] focus:ring-[#8B6914]"
                  />
                  <div>
                    <span className="block font-bold text-sm" style={{ fontFamily: 'Manrope, sans-serif', color: 'var(--admin-text)' }}>
                      Photographer Upload (All File Types)
                    </span>
                    <span className="text-xs" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
                      Allows uploading any file type including RAW files (.NEF, .CR2, .CR3, .ARW etc). Use this for second shooters or photographers — not for wedding guests.
                    </span>
                  </div>
                </label>
              </div>
            )}
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Expiry Date (optional)</Label>
              <Popover open={expiryPickerOpen} onOpenChange={setExpiryPickerOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" data-testid="expiry-date-picker"
                    className={`w-full justify-start text-left font-normal border-[#D4D4D8] rounded-sm ${!shareForm.expires_at ? 'text-[#A8A29E]' : ''}`}>
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {shareForm.expires_at 
                      ? new Date(shareForm.expires_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
                      : "No expiry - link never expires"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={shareForm.expires_at ? new Date(shareForm.expires_at) : undefined}
                    onSelect={(date) => {
                      setShareForm(f => ({...f, expires_at: date ? date.toISOString() : null}));
                      setExpiryPickerOpen(false);
                    }}
                    disabled={(date) => date < new Date()}
                    initialFocus
                  />
                  {shareForm.expires_at && (
                    <div className="p-2 border-t">
                      <Button variant="ghost" size="sm" className="w-full text-xs" 
                        onClick={() => { setShareForm(f => ({...f, expires_at: null})); setExpiryPickerOpen(false); }}>
                        Remove expiry date
                      </Button>
                    </div>
                  )}
                </PopoverContent>
              </Popover>
              <p className="text-xs text-[#A8A29E]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                You can also manually expire shares anytime from the shares list
              </p>
            </div>
            <Button data-testid="create-share-submit" onClick={handleCreateShare} disabled={creatingShare}
              className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-5 text-xs tracking-[0.15em] uppercase font-bold">
              {creatingShare ? "Creating..." : "Create Share Link"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* QR Code Dialog */}
      <Dialog open={!!showQR} onOpenChange={() => setShowQR(null)}>
        <DialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none max-w-md" style={{ backgroundColor: 'var(--admin-bg)' }}>
          <DialogHeader className="text-center">
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>QR Code</DialogTitle>
            <DialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>{showQR?.label}</DialogDescription>
          </DialogHeader>
          {showQR && (
            <div className="flex flex-col items-center gap-4 py-4">
              <img src={`${getShareQR(showQR.id)}&token=${localStorage.getItem('admin_token')}`}
                alt="QR Code" className="w-48 h-48" data-testid="qr-code-image" />
              <p className="text-sm font-medium break-all text-center" style={{ color: 'var(--admin-text)', fontFamily: 'Manrope, sans-serif' }}>
                {window.location.origin}/s/{showQR.token}
              </p>
              <Button onClick={() => copyShareLink(showQR.token)} className="w-full bg-[#1C1917] text-[#FDFCF8] rounded-sm px-6 py-2 text-xs tracking-wider uppercase font-bold gap-2">
                <Copy className="w-3.5 h-3.5" /> Copy Link
              </Button>

              {/* QR Frame Design Selector */}
              <div className="w-full pt-2 border-t" style={{ borderColor: 'var(--admin-border)' }}>
                <p className="text-xs tracking-wider uppercase font-bold mb-3 text-center" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
                  Download Printable QR Frame
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 1, name: 'Botanical', desc: 'Gold leaf corners' },
                    { id: 2, name: 'Hearts', desc: 'Romantic love theme' },
                    { id: 3, name: 'Minimal', desc: 'Clean & elegant' },
                  ].map(d => (
                    <button
                      key={d.id}
                      data-testid={`qr-design-${d.id}`}
                      onClick={() => window.open(getShareQRFrame(showQR.id, d.id), '_blank')}
                      className="group flex flex-col items-center gap-1.5 p-2 border text-center transition-all hover:border-[#D4AF37] hover:bg-[#D4AF37]/5 overflow-hidden"
                      style={{ borderColor: 'var(--admin-border)', fontFamily: 'Manrope, sans-serif' }}
                    >
                      <div className="w-full aspect-[4/3] rounded-sm overflow-hidden bg-[#F5F2EB] mb-1">
                        <img
                          src={getQRDesignPreview(d.id)}
                          alt={`${d.name} design preview`}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      </div>
                      <span className="text-xs font-bold" style={{ color: 'var(--admin-text)' }}>{d.name}</span>
                      <span className="text-[10px] leading-tight" style={{ color: 'var(--admin-faint)' }}>{d.desc}</span>
                      <div className="flex items-center gap-1 text-[10px] font-bold tracking-wider uppercase text-[#D4AF37] opacity-0 group-hover:opacity-100 transition-opacity">
                        <Download className="w-3 h-3" /> PDF
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Edit Share Dialog */}
      <Dialog open={!!editingShare} onOpenChange={(open) => { if (!open) setEditingShare(null); }}>
        <DialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none max-w-md" style={{ backgroundColor: 'var(--admin-bg)' }}>
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Edit Share</DialogTitle>
            <DialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
              {editingShare && <span className="text-xs break-all">{window.location.origin}/s/{editingShare.token}</span>}
            </DialogDescription>
          </DialogHeader>
          {editingShare && (
            <div className="space-y-4 py-2" style={{ fontFamily: 'Manrope, sans-serif' }}>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Label</Label>
                <Input data-testid="edit-share-label" value={editForm.label} onChange={e => setEditForm(f => ({...f, label: e.target.value}))}
                  className="border-[#D4D4D8] rounded-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Password</Label>
                <div className="flex gap-2">
                  <Input data-testid="edit-share-password" name="edit-share-password" autoComplete="new-password" data-lpignore="true"
                    value={editForm.password} onChange={e => setEditForm(f => ({...f, password: e.target.value}))}
                    placeholder="Leave blank to remove password" className="border-[#D4D4D8] rounded-sm flex-1" />
                  <Button type="button" variant="outline" size="sm" data-testid="edit-generate-password-btn"
                    className="shrink-0 text-xs gap-1.5 border-[#D4D4D8] hover:bg-[#F5F2EB]"
                    onClick={() => {
                      const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
                      let pw = '';
                      for (let i = 0; i < 8; i++) pw += chars[Math.floor(Math.random() * chars.length)];
                      setEditForm(f => ({...f, password: pw}));
                    }}>
                    <RefreshCw className="w-3.5 h-3.5" /> Generate
                  </Button>
                </div>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Access Level</Label>
                <select data-testid="edit-share-access" value={editForm.access_level}
                  onChange={e => setEditForm(f => ({...f, access_level: e.target.value}))}
                  className="w-full border border-[#D4D4D8] rounded-sm p-2 text-sm bg-white" style={{ fontFamily: 'Manrope, sans-serif' }}>
                  <option value="view">View Only</option>
                  <option value="download">Download</option>
                  <option value="upload">Upload</option>
                  <option value="full">Full Access</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <Button onClick={() => setEditingShare(null)} variant="outline" className="flex-1 rounded-sm text-xs tracking-wider uppercase font-bold border-[#D4D4D8]">
                  Cancel
                </Button>
                <Button data-testid="save-share-btn" onClick={handleSaveShare} className="flex-1 bg-[#1C1917] text-[#FDFCF8] rounded-sm text-xs tracking-wider uppercase font-bold">
                  Save Changes
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Add Folder Dialog */}
      <Dialog open={showAddFolderDialog} onOpenChange={(open) => {
        setShowAddFolderDialog(open);
        if (!open) setNewFolderName("");
      }}>
        <DialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none max-w-md" style={{ backgroundColor: 'var(--admin-bg)' }}>
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Add Folder</DialogTitle>
            <DialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
              Add an empty folder to {gallery?.folder_name}. Existing files and folders will not be changed.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="flex flex-wrap gap-2">
              {STANDARD_SUBFOLDERS.filter(name => !gallery?.subfolders?.some(existing => existing.toLowerCase() === name.toLowerCase())).map(name => (
                <Button key={name} type="button" variant="outline" size="sm"
                  onClick={() => setNewFolderName(name)}
                  className="rounded-sm text-xs border-[#D4D4D8] hover:border-[#D4AF37]">
                  {name}
                </Button>
              ))}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-subfolder-name" className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Folder name</Label>
              <Input id="new-subfolder-name" data-testid="new-subfolder-name" value={newFolderName}
                onChange={e => setNewFolderName(e.target.value)} placeholder="e.g. Album Favourites" autoFocus
                className="border-[#D4D4D8] rounded-sm"
                onKeyDown={e => { if (e.key === 'Enter' && !creatingFolder) handleCreateSubfolder(); }} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddFolderDialog(false)} className="rounded-sm">Cancel</Button>
            <Button data-testid="confirm-add-subfolder" onClick={handleCreateSubfolder}
              disabled={!newFolderName.trim() || creatingFolder}
              className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-6 text-xs tracking-wider uppercase font-bold gap-2">
              <Plus className="w-3.5 h-3.5" /> {creatingFolder ? "Adding..." : "Add Folder"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Subfolder Confirmation */}
      <AlertDialog open={!!deleteSubfolderTarget} onOpenChange={(open) => { if (!open) setDeleteSubfolderTarget(null); }}>
        <AlertDialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none" style={{ backgroundColor: 'var(--admin-bg)' }}>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Remove &ldquo;{deleteSubfolderTarget}&rdquo;?
            </AlertDialogTitle>
            <AlertDialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
              {((gallery?.file_counts || {})[deleteSubfolderTarget] || 0) > 0
                ? `This will permanently delete ${(gallery?.file_counts || {})[deleteSubfolderTarget]} files in this folder.`
                : "This will remove the empty subfolder from this gallery."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm" style={{ fontFamily: 'Manrope, sans-serif' }}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-subfolder"
              onClick={confirmDeleteSubfolder}
              className="bg-[#9F1239] text-white hover:bg-[#9F1239]/90 rounded-sm text-xs tracking-wider uppercase font-bold"
              style={{ fontFamily: 'Manrope, sans-serif' }}
            >
              Remove Folder
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Image-first Gallery Ready check */}
      <Dialog open={showReadiness} onOpenChange={(open) => { if (!sendingNotification) setShowReadiness(open); }}>
        <DialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none max-w-xl max-h-[90vh] overflow-y-auto" style={{ backgroundColor: 'var(--admin-bg)' }} data-testid="gallery-readiness-dialog">
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium flex items-center gap-2" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              <ShieldCheck className="w-6 h-6 text-[#D4AF37]" /> Gallery Ready Check
            </DialogTitle>
            <DialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
              A final photograph-only check before the couple receives their gallery email. Videos never delay this step.
            </DialogDescription>
          </DialogHeader>

          {checkingReadiness ? (
            <div className="py-12 text-center">
              <RefreshCw className="w-7 h-7 mx-auto mb-3 text-[#D4AF37] animate-spin" />
              <p className="text-sm" style={{ color: 'var(--admin-muted)' }}>Checking photographs, share link and backup…</p>
            </div>
          ) : galleryReadiness && (
            <div className="space-y-4 mt-2">
              <div className="p-4 border rounded-sm flex items-start gap-3"
                style={{
                  borderColor: galleryReadiness.ready ? '#86EFAC' : '#FCA5A5',
                  backgroundColor: galleryReadiness.ready ? 'rgba(22,163,74,0.08)' : 'rgba(185,28,28,0.08)'
                }}>
                {galleryReadiness.ready
                  ? <CheckCircle2 className="w-6 h-6 shrink-0 text-green-700" />
                  : <XCircle className="w-6 h-6 shrink-0 text-red-700" />}
                <div>
                  <p className="font-semibold" style={{ color: 'var(--admin-text)' }}>
                    {galleryReadiness.ready ? 'Ready to notify the couple' : 'Please fix the blocked items first'}
                  </p>
                  <p className="text-xs mt-1" style={{ color: 'var(--admin-muted)' }}>
                    {galleryReadiness.warnings > 0
                      ? `${galleryReadiness.warnings} advisory warning${galleryReadiness.warnings === 1 ? '' : 's'} — warnings do not stop you sending.`
                      : 'All image-delivery checks passed.'}
                  </p>
                </div>
              </div>

              <div className="border rounded-sm divide-y" style={{ borderColor: 'var(--admin-border)' }}>
                {galleryReadiness.checks.map(item => {
                  const ItemIcon = item.status === 'healthy' ? CheckCircle2 : item.status === 'warning' ? AlertTriangle : XCircle;
                  const colour = item.status === 'healthy' ? '#15803D' : item.status === 'warning' ? '#B45309' : '#B91C1C';
                  return (
                    <div key={item.key} className="p-3 flex items-start gap-3" style={{ borderColor: 'var(--admin-border)' }} data-testid={`readiness-${item.key}`}>
                      <ItemIcon className="w-4 h-4 shrink-0 mt-0.5" style={{ color: colour }} />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold" style={{ color: 'var(--admin-text)' }}>{item.title}</p>
                        <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--admin-faint)' }}>{item.detail}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="p-4 rounded-sm border space-y-2" style={{ borderColor: 'var(--admin-border)', backgroundColor: 'var(--admin-surface-soft)' }}>
                <p className="text-[10px] tracking-[0.12em] uppercase font-bold" style={{ color: 'var(--admin-faint)' }}>Email preview</p>
                <p className="text-xs"><strong>To:</strong> {galleryReadiness.preview.recipient || 'Not set'}</p>
                <p className="text-xs break-all"><strong>Link:</strong> {galleryReadiness.preview.gallery_link || 'Not available'}</p>
                <p className="text-xs"><strong>Password:</strong> {galleryReadiness.preview.password}</p>
              </div>
            </div>
          )}

          <DialogFooter className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => setShowReadiness(false)} disabled={sendingNotification} className="rounded-sm">Cancel</Button>
            <Button data-testid="confirm-gallery-notification" onClick={handleConfirmNotification}
              disabled={!galleryReadiness?.ready || checkingReadiness || sendingNotification}
              className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-6 text-xs tracking-wider uppercase font-bold gap-2">
              <Mail className="w-3.5 h-3.5" /> {sendingNotification ? 'Sending…' : 'Send Gallery Email'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* File Delete Confirmation Dialog */}
      <Dialog open={fileDeleteConfirm.open} onOpenChange={(open) => !open && setFileDeleteConfirm({ open: false, fileId: null, filename: "", deleteBackup: false, isBulk: false })}>
        <DialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none max-w-md" style={{ backgroundColor: 'var(--admin-bg)' }}>
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Delete {fileDeleteConfirm.isBulk ? "Files" : "File"}
            </DialogTitle>
            <DialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
              Are you sure you want to delete <strong>{fileDeleteConfirm.filename}</strong>?
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2">
            <label className="flex items-start gap-3 p-3 rounded-sm border cursor-pointer hover:bg-amber-50/50 transition-colors" style={{ borderColor: 'var(--admin-border)' }}>
              <input data-testid="delete-file-backup-checkbox" type="checkbox" checked={fileDeleteConfirm.deleteBackup}
                onChange={e => setFileDeleteConfirm(d => ({...d, deleteBackup: e.target.checked}))}
                className="mt-0.5 w-4 h-4 rounded accent-[#D4AF37]" />
              <div>
                <span className="text-sm font-semibold" style={{ color: 'var(--admin-text)', fontFamily: 'Manrope, sans-serif' }}>Also delete from backup</span>
                <p className="text-xs mt-0.5" style={{ color: 'var(--admin-faint)', fontFamily: 'Manrope, sans-serif' }}>
                  Removes the backup copy too, freeing up storage space
                </p>
              </div>
            </label>
          </div>
          <DialogFooter className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => setFileDeleteConfirm({ open: false, fileId: null, filename: "", deleteBackup: false, isBulk: false })}
              className="flex-1 rounded-sm border-[#D4D4D8] text-xs tracking-wider">
              Cancel
            </Button>
            <Button data-testid="confirm-delete-file" onClick={confirmFileDelete}
              className="flex-1 bg-[#9F1239] text-white hover:bg-[#9F1239]/90 rounded-sm text-xs tracking-wider">
              <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete{fileDeleteConfirm.deleteBackup ? " + Backup" : ""}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Send Template Email Dialog */}
      <Dialog open={showSendEmail} onOpenChange={setShowSendEmail}>
        <DialogContent className="admin-mobile-dialog border-none shadow-2xl rounded-none max-w-md" style={{ backgroundColor: 'var(--admin-bg)' }}>
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Send Email</DialogTitle>
            <DialogDescription style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>
              Send a template email to <strong>{clientEmail}</strong>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {emailTemplates.length === 0 ? (
              <div className="text-center py-6 border rounded-sm" style={{ borderColor: 'var(--admin-border)' }}>
                <FileText className="w-10 h-10 mx-auto mb-2 text-[#D4D4D8]" />
                <p className="text-sm" style={{ color: 'var(--admin-muted)', fontFamily: 'Manrope, sans-serif' }}>No templates found</p>
                <p className="text-xs mt-1" style={{ color: 'var(--admin-faint)' }}>Create templates in Settings &gt; Email Templates first</p>
              </div>
            ) : (
              <>
                <div className="space-y-1.5">
                  <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Choose Template</Label>
                  <div className="space-y-2">
                    {emailTemplates.map(t => (
                      <label key={t.id} className={`flex items-start gap-3 p-3 rounded-sm border cursor-pointer transition-colors ${
                        selectedTemplateId === t.id ? 'border-[#D4AF37] bg-[#D4AF37]/5' : 'border-[#E8E4DC] hover:bg-[#FAFAF9]'
                      }`} data-testid={`template-option-${t.id}`}>
                        <input type="radio" name="template" value={t.id} checked={selectedTemplateId === t.id}
                          onChange={() => setSelectedTemplateId(t.id)}
                          className="mt-0.5 accent-[#D4AF37]" />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-semibold" style={{ color: 'var(--admin-text)', fontFamily: 'Manrope, sans-serif' }}>{t.name}</span>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--admin-faint)', fontFamily: 'Manrope, sans-serif' }}>
                            Subject: {t.subject.replace('{couple_name}', gallery?.folder_name || '')}
                          </p>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
                {selectedTemplateId && (
                  <div className="p-3 rounded-sm border text-xs" style={{ borderColor: 'var(--admin-border)', backgroundColor: 'var(--admin-surface-soft)', fontFamily: 'Manrope, sans-serif' }}>
                    <p className="font-semibold mb-1" style={{ color: 'var(--admin-muted)' }}>Preview:</p>
                    <p style={{ color: 'var(--admin-subtle)', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                      {(emailTemplates.find(t => t.id === selectedTemplateId)?.body || '')
                        .replace(/\{couple_name\}/g, gallery?.folder_name || '')
                        .replace(/\{gallery_link\}/g, shares.find(s => s.is_active && !s.guest_upload_mode)?.custom_slug || shares.find(s => s.is_active && !s.guest_upload_mode)?.token || '')
                        .slice(0, 300)}{(emailTemplates.find(t => t.id === selectedTemplateId)?.body || '').length > 300 ? '...' : ''}
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
          <div className="space-y-1.5 px-0">
            <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: 'var(--admin-muted)' }}>Attachment</Label>
            <input ref={attachmentInputRef} type="file" className="hidden" data-testid="gallery-email-attachment"
              onChange={e => { if (e.target.files?.length) { setGalleryEmailAttachments(prev => [...prev, ...Array.from(e.target.files)]); } e.target.value = ''; }} />
            <div className="flex items-center gap-2 flex-wrap">
              <button type="button" onClick={() => attachmentInputRef.current?.click()}
                className="cursor-pointer text-xs px-3 py-1.5 border rounded-sm hover:bg-[#F5F2EB] flex items-center gap-1.5"
                style={{ borderColor: 'var(--admin-border-strong)', fontFamily: 'Manrope, sans-serif' }}
                data-testid="gallery-email-choose-file">
                <Paperclip className="w-3.5 h-3.5" />Choose File
              </button>
              {galleryEmailAttachments.map((f, i) => (
                <span key={i} className="text-[11px] px-2 py-1 rounded-full flex items-center gap-1.5 border" style={{ backgroundColor: 'var(--admin-surface-raised)', borderColor: 'var(--admin-border-strong)', color: 'var(--admin-text)' }}>
                  <Paperclip className="w-3 h-3" style={{ color: '#D4AF37' }} />
                  {f.name} <span style={{ color: 'var(--admin-faint)' }}>({(f.size / 1024).toFixed(0)}KB)</span>
                  <button type="button" onClick={() => setGalleryEmailAttachments(prev => prev.filter((_, j) => j !== i))} className="hover:text-red-600 ml-0.5"><X className="w-3 h-3" /></button>
                </span>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowSendEmail(false)} className="rounded-sm">Cancel</Button>
            <Button data-testid="confirm-send-template" onClick={handleSendTemplateEmail}
              disabled={!selectedTemplateId || sendingTemplate || emailTemplates.length === 0}
              className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-6 text-xs tracking-wider uppercase font-bold gap-2">
              <Send className="w-3.5 h-3.5" /> {sendingTemplate ? "Sending..." : "Send"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
