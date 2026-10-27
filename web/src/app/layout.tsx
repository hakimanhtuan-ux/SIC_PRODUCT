import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TrueCheck AI – Kiểm chứng tại điểm chạm, tin tưởng dựa trên bằng chứng",
  description:
    "Nền tảng kiểm chứng thông tin dựa trên bằng chứng (Evidence-Based AI Verification) dành cho văn bản, tài liệu PDF/DOCX và URL tiếng Việt.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}

