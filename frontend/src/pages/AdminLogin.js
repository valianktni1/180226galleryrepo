import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Camera, Lock, User, Eye, EyeOff } from "lucide-react";
import { checkSetup, setupAdmin, loginAdmin } from "@/lib/api";

// Check if JWT token is expired
function isTokenExpired(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

export default function AdminLogin() {
  const navigate = useNavigate();
  const [isSetup, setIsSetup] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [needs2FA, setNeeds2FA] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [form, setForm] = useState({ username: "", password: "", display_name: "Weddings By Mark" });

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (token) {
      // Check if token is expired
      if (isTokenExpired(token)) {
        localStorage.removeItem("admin_token");
        toast.info("Session expired. Please log in again.");
      } else {
        navigate("/admin/dashboard");
        return;
      }
    }
    checkSetup().then(r => setNeedsSetup(!r.data.setup_complete)).catch(() => setNeedsSetup(true));
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      let res;
      if (needsSetup) {
        res = await setupAdmin(form);
      } else {
        res = await loginAdmin({ 
          username: form.username, 
          password: form.password,
          totp_code: needs2FA ? totpCode : undefined
        });
      }
      
      // Check if 2FA is required
      if (res.data.requires_2fa) {
        setNeeds2FA(true);
        setLoading(false);
        return;
      }
      
      localStorage.setItem("admin_token", res.data.token);
      toast.success("Welcome back");
      navigate("/admin/dashboard");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Authentication failed");
      if (needs2FA) {
        setTotpCode("");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setNeeds2FA(false);
    setTotpCode("");
  };

  if (needsSetup === null) return null;

  return (
    <div className="min-h-screen flex relative noise-bg" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Left - Hero Image */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <img
          src="https://images.unsplash.com/photo-1624635446269-ea81d79bbc30?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA0MTJ8MHwxfHNlYXJjaHwyfHx3ZWRkaW5nJTIwY291cGxlJTIwc3Vuc2V0JTIwcm9tYW50aWMlMjBhcnRpc3RpY3xlbnwwfHx8fDE3NzEzNjM2MTR8MA&ixlib=rb-4.1.0&q=85"
          alt="Wedding couple at sunset"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-black/20" />
        <div className="absolute bottom-12 left-12 right-12 text-white">
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="text-sm tracking-[0.2em] uppercase font-semibold mb-3"
            style={{ fontFamily: 'Manrope, sans-serif' }}
          >
            Gallery Admin
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="text-5xl font-light italic leading-tight"
            style={{ fontFamily: 'Cormorant Garamond, serif' }}
          >
            Couples Gallery<br />Management System
          </motion.h1>
        </div>
      </div>

      {/* Right - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 lg:p-16">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          <div className="flex items-center gap-3 mb-16">
            <img src="/logo.png" alt="Weddings By Mark" className="h-10" style={{ filter: 'invert(1)' }} />
          </div>

          <h2
            className="text-4xl md:text-5xl mb-3 font-medium"
            style={{ fontFamily: 'Cormorant Garamond, serif' }}
          >
            {needs2FA ? "Verification" : needsSetup ? "Set Up" : "Sign In"}
          </h2>
          <p className="text-base mb-12" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
            {needs2FA 
              ? "Enter the 6-digit code from your Google Authenticator app" 
              : needsSetup 
                ? "Create your admin account to get started" 
                : "Enter your credentials to continue"}
          </p>

          <form onSubmit={handleSubmit} className="space-y-8">
            {needs2FA ? (
              /* 2FA Code Input */
              <>
                <div className="space-y-2">
                  <Label className="text-xs tracking-[0.15em] uppercase font-semibold" style={{ color: '#57534E' }}>
                    Authentication Code
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-0 top-3.5 w-4 h-4 text-[#A8A29E]" />
                    <Input
                      data-testid="totp-code"
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9A-Fa-f]*"
                      maxLength={8}
                      autoComplete="one-time-code"
                      autoFocus
                      value={totpCode}
                      onChange={e => setTotpCode(e.target.value.replace(/[^0-9A-Fa-f]/g, ''))}
                      className="border-0 border-b border-[#D4D4D8] bg-transparent rounded-none pl-6 pr-0 py-3 focus-visible:ring-0 focus-visible:border-[#1C1917] placeholder:text-[#A8A29E] text-2xl tracking-[0.5em] text-center"
                      style={{ fontFamily: 'monospace' }}
                      placeholder="000000"
                      required
                    />
                  </div>
                  <p className="text-xs mt-2" style={{ color: '#A8A29E', fontFamily: 'Manrope, sans-serif' }}>
                    Or enter a recovery code
                  </p>
                </div>

                <Button
                  data-testid="verify-2fa-btn"
                  type="submit"
                  disabled={loading || totpCode.length < 6}
                  className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-6 text-xs tracking-[0.2em] uppercase font-bold"
                  style={{ transition: 'background-color 0.3s ease', fontFamily: 'Manrope, sans-serif' }}
                >
                  {loading ? "Verifying..." : "Verify"}
                </Button>

                <button
                  type="button"
                  onClick={handleBack}
                  className="w-full text-center text-sm text-[#57534E] hover:text-[#1C1917]"
                  style={{ fontFamily: 'Manrope, sans-serif' }}
                >
                  Back to sign in
                </button>
              </>
            ) : (
              /* Normal Login Form */
              <>
            {needsSetup && (
              <div className="space-y-2">
                <Label className="text-xs tracking-[0.15em] uppercase font-semibold" style={{ color: '#57534E' }}>
                  Display Name
                </Label>
                <Input
                  data-testid="setup-display-name"
                  value={form.display_name}
                  onChange={e => setForm(f => ({...f, display_name: e.target.value}))}
                  className="border-0 border-b border-[#D4D4D8] bg-transparent rounded-none px-0 py-3 focus-visible:ring-0 focus-visible:border-[#1C1917] placeholder:text-[#A8A29E] text-base"
                  style={{ fontFamily: 'Manrope, sans-serif' }}
                  placeholder="Your business name"
                />
              </div>
            )}

            <div className="space-y-2">
              <Label className="text-xs tracking-[0.15em] uppercase font-semibold" style={{ color: '#57534E' }}>
                Username
              </Label>
              <div className="relative">
                <User className="absolute left-0 top-3.5 w-4 h-4 text-[#A8A29E]" />
                <Input
                  data-testid="login-username"
                  value={form.username}
                  onChange={e => setForm(f => ({...f, username: e.target.value}))}
                  className="border-0 border-b border-[#D4D4D8] bg-transparent rounded-none pl-6 pr-0 py-3 focus-visible:ring-0 focus-visible:border-[#1C1917] placeholder:text-[#A8A29E] text-base"
                  style={{ fontFamily: 'Manrope, sans-serif' }}
                  placeholder="Enter username"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-xs tracking-[0.15em] uppercase font-semibold" style={{ color: '#57534E' }}>
                Password
              </Label>
              <div className="relative">
                <Lock className="absolute left-0 top-3.5 w-4 h-4 text-[#A8A29E]" />
                <Input
                  data-testid="login-password"
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={e => setForm(f => ({...f, password: e.target.value}))}
                  className="border-0 border-b border-[#D4D4D8] bg-transparent rounded-none pl-6 pr-10 py-3 focus-visible:ring-0 focus-visible:border-[#1C1917] placeholder:text-[#A8A29E] text-base"
                  style={{ fontFamily: 'Manrope, sans-serif' }}
                  placeholder="Enter password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(s => !s)}
                  className="absolute right-0 top-3 text-[#A8A29E] hover:text-[#1C1917]"
                  style={{ transition: 'color 0.2s ease' }}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button
              data-testid="login-submit-btn"
              type="submit"
              disabled={loading}
              className="w-full bg-[#1C1917] text-[#FDFCF8] hover:bg-[#1C1917]/90 rounded-sm px-8 py-6 text-xs tracking-[0.2em] uppercase font-bold"
              style={{ transition: 'background-color 0.3s ease, transform 0.2s ease', fontFamily: 'Manrope, sans-serif' }}
            >
              {loading ? "Please wait..." : (needsSetup ? "Create Account" : "Sign In")}
            </Button>
              </>
            )}
          </form>
        </motion.div>
      </div>
    </div>
  );
}
