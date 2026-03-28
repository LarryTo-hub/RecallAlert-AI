import { NavLink } from "react-router-dom";

interface Props {
  variant: "sidebar" | "bottom";
}

const links = [
  { to: "/dashboard", label: "Dashboard", icon: "🏠" },
  { to: "/pantry", label: "Pantry", icon: "🛒" },
  { to: "/alerts", label: "Alerts", icon: "🔔" },
  { to: "/search", label: "Search", icon: "🔍" },
  { to: "/notifications", label: "Notify", icon: "📱" },
  { to: "/settings", label: "Settings", icon: "⚙️" },
];

function NavItem({
  to,
  label,
  icon,
  compact,
}: {
  to: string;
  label: string;
  icon: string;
  compact: boolean;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors
        ${isActive
          ? "bg-red-50 text-primary"
          : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        }
        ${compact ? "flex-col gap-0.5 px-0 py-1 text-xs" : ""}`
      }
      aria-label={label}
    >
      <span className={compact ? "text-xl" : "text-base"} aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </NavLink>
  );
}

export default function NavBar({ variant }: Props) {
  if (variant === "sidebar") {
    return (
      <nav
        className="hidden md:flex flex-col w-56 shrink-0 bg-white border-r border-gray-200 p-4 gap-1"
        aria-label="Main navigation"
      >
        {/* Logo */}
        <div className="flex items-center gap-2 mb-6 px-3">
          <span className="text-2xl" aria-hidden="true">🔔</span>
          <span className="font-bold text-gray-900 text-sm leading-tight">
            RecallAlert <span className="text-primary">AI</span>
          </span>
        </div>

        {links.map((l) => (
          <NavItem key={l.to} {...l} compact={false} />
        ))}
      </nav>
    );
  }

  // Bottom nav for mobile
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t border-gray-200 flex items-center justify-around px-2 safe-pb z-40"
      aria-label="Main navigation"
      style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
    >
      {links.map((l) => (
        <NavItem key={l.to} {...l} compact={true} />
      ))}
    </nav>
  );
}
