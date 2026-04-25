import { NavLink } from "react-router-dom";
import { useTranslation } from "@/i18n/LanguageContext";

interface Props {
  variant: "sidebar" | "bottom";
}

function HomeIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
  );
}
function PantryIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
    </svg>
  );
}
function AlertIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  );
}
function MailIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}
function CogIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}
function ShieldIcon() {
  return (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={1.75} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}

const links = [
  { to: "/dashboard", label: "nav.dashboard", Icon: HomeIcon },
  { to: "/pantry",    label: "nav.pantry",    Icon: PantryIcon },
  { to: "/alerts",   label: "nav.alerts",    Icon: AlertIcon },
  { to: "/notifications", label: "nav.notify", Icon: MailIcon },
  { to: "/settings", label: "nav.settings",  Icon: CogIcon },
];

function NavItem({
  to,
  label,
  Icon,
  compact,
}: {
  to: string;
  label: string;
  Icon: () => JSX.Element;
  compact: boolean;
}) {
  const { t } = useTranslation();
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150
        ${isActive
          ? "bg-primary/15 text-primary border-l-2 border-primary"
          : "text-slate-400 hover:bg-navy-700 hover:text-white border-l-2 border-transparent"
        }
        ${compact ? "flex-col gap-1 px-0 py-2 text-[10px] border-l-0 border-b-0 rounded-none" : ""}`
      }
      aria-label={t(label)}
    >
      <Icon />
      <span>{t(label)}</span>
    </NavLink>
  );
}

export default function NavBar({ variant }: Props) {
  if (variant === "sidebar") {
    return (
      <nav
        className="hidden md:flex flex-col w-56 shrink-0 bg-navy-950 border-r border-navy-700 p-4 gap-0.5"
        aria-label="Main navigation"
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 mb-8 px-3">
          <ShieldIcon />
          <span className="font-bold text-white text-sm leading-tight tracking-wide">
            Recall<span className="text-primary">Alert</span>{" "}
            <span className="text-primary-light font-light">AI</span>
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
      className="md:hidden fixed bottom-0 inset-x-0 bg-navy-950 border-t border-navy-700 flex items-center justify-around px-2 safe-pb z-40"
      aria-label="Main navigation"
      style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
    >
      {links.map((l) => (
        <NavItem key={l.to} {...l} compact={true} />
      ))}
    </nav>
  );
}
