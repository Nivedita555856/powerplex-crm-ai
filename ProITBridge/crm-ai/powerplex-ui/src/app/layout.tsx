import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar }  from "@/components/layout/TopBar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title:       "PowerPlex — Enterprise AI CRM",
  description: "Agentic RAG + AI Agents + MCTS + Automation Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <TopBar />
        <div className="flex h-[calc(100vh-56px)]">
          <Sidebar />
          <main className="flex-1 overflow-y-auto bg-[#F5F3FF]">{children}</main>
        </div>
      </body>
    </html>
  );
}
