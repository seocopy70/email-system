import type { Metadata } from "next";
import { Noto_Sans_KR, Noto_Serif_KR } from "next/font/google";
import "./globals.css";

// CJK 웹폰트는 next/font의 preload를 지원하지 않아 weight만 지정하고 preload를 끕니다.
const sans = Noto_Sans_KR({
  weight: ["400", "500", "600", "700"],
  preload: false,
  variable: "--font-sans",
});
const serif = Noto_Serif_KR({
  weight: ["500", "600", "700"],
  preload: false,
  variable: "--font-serif",
});

export const metadata: Metadata = {
  title: "기업 이메일 발송 시스템",
  description: "맞춤 메일 작성 · 중복 발송 방지",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={`${sans.variable} ${serif.variable}`}>
      <body>{children}</body>
    </html>
  );
}
