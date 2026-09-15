import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "wbm_admin_theme";

export default function AdminThemeToggle() {
  const [dark, setDark] = useState(() => localStorage.getItem(STORAGE_KEY) === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("admin-dark", dark);
    localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
    return () => document.documentElement.classList.remove("admin-dark");
  }, [dark]);

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={() => setDark(value => !value)}
      className="admin-theme-toggle gap-2 rounded-sm text-xs tracking-wider"
      title={dark ? "Use light admin theme" : "Use dark admin theme"}
      aria-label={dark ? "Use light admin theme" : "Use dark admin theme"}
      data-testid="admin-theme-toggle"
    >
      {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
      <span className="hidden xl:inline">{dark ? "Light" : "Dark"}</span>
    </Button>
  );
}
