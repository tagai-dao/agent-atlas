import type { Metadata } from "next";
import "./globals.css";
import "./atlas-theme.css";

export const metadata: Metadata = {
  title: "Agent Atlas · Agent ID 身份查询",
  description: "查询 .ai Agent ID、链上钱包与 X 公开声明，每条关联均可追溯证据。",
  icons: {
    icon: "/tagai-favicon.ico",
    shortcut: "/tagai-favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
