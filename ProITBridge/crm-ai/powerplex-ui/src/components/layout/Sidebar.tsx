"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/console",      label: "AI Support Console",       icon: "◈" },
  { href: "/tickets",      label: "Ticket Dashboard",         icon: "⧉" },
  { href: "/approvals",    label: "Approval Center",          icon: "✓" },
  { href: "/automation",   label: "Automation Dashboard",     icon: "⚙" },
  { href: "/customers",    label: "Customer Intelligence",    icon: "◎" },
  { href: "/technicians",  label: "Technician Dashboard",     icon: "⊕" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 bg-white border-r border-[#DDD6FE] flex flex-col shrink-0">
      <div className="p-4 border-b border-[#EDE9FE]">
        <p className="text-xs font-bold text-[#9CA3AF] uppercase tracking-widest">Navigation</p>
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all
              ${path.startsWith(n.href)
                ? "bg-[#EDE9FE] text-[#6C4FF8] font-semibold"
                : "text-[#4B5563] hover:bg-[#F5F3FF] hover:text-[#6C4FF8]"}`}>
            <span className="text-base w-5 text-center">{n.icon}</span>
            <span className="leading-tight">{n.label}</span>
          </Link>
        ))}
      </nav>
      <div className="p-3 border-t border-[#EDE9FE]">
        <div className="text-xs text-[#9CA3AF] text-center">PowerPlex v1.0</div>
      </div>
    </aside>
  );
}
