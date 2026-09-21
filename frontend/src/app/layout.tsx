import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "기업 이메일 발송 시스템",
  description: "맞춤 메일 작성 · 중복 발송 방지",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
