import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FactCheck Assistent – Kiểm chứng tại điểm chạm, tin tưởng dựa trên bằng chứng",
  description:
    "Nền tảng kiểm chứng thông tin & giám định hình ảnh dựa trên bằng chứng (Evidence-Based FactCheck Assistent).",
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

