import type { Metadata } from "next";
import "./globals.css";
import Navigation from "@/components/Navigation";
import HealthBadge from "@/components/HealthBadge";

export const metadata: Metadata = {
  title: "Keith's Crypto Agent Dashboard",
  description: "Autonomous AI trading agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
          <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
            <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Keith's Crypto Agent
              </h1>
              <HealthBadge />
            </div>
          </header>
          <Navigation />
          <main className="max-w-7xl mx-auto px-4 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
