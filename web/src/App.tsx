import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import NavBar from "@/components/NavBar";
import InstallPrompt from "@/components/InstallPrompt";
import Dashboard from "@/pages/Dashboard";
import Pantry from "@/pages/Pantry";
import Alerts from "@/pages/Alerts";
import Notifications from "@/pages/Notifications";
import Search from "@/pages/Search";
import Settings from "@/pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-gray-50">
        {/* Sidebar nav — visible on md+ */}
        <NavBar variant="sidebar" />

        {/* Main content area */}
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/pantry" element={<Pantry />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/search" element={<Search />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>

        {/* Bottom nav — visible on mobile */}
        <NavBar variant="bottom" />

        <InstallPrompt />
      </div>
    </BrowserRouter>
  );
}
