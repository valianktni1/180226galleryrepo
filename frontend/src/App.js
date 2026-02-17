import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import AdminLogin from "@/pages/AdminLogin";
import AdminDashboard from "@/pages/AdminDashboard";
import AdminGalleryDetail from "@/pages/AdminGalleryDetail";
import ClientAccess from "@/pages/ClientAccess";
import ClientGallery from "@/pages/ClientGallery";

function App() {
  return (
    <div className="min-h-screen">
      <BrowserRouter>
        <Routes>
          <Route path="/admin" element={<AdminLogin />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
          <Route path="/admin/gallery/:id" element={<AdminGalleryDetail />} />
          <Route path="/gallery/:slug" element={<ClientAccess />} />
          <Route path="/gallery/:slug/view" element={<ClientGallery />} />
          <Route path="/" element={<AdminLogin />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="bottom-right" />
    </div>
  );
}

export default App;
