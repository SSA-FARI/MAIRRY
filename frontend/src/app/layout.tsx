import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "MAIRRY",
  description: "계약서부터 잔금까지 관리하는 AI 자금 플래너",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
