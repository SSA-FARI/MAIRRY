import Link from "next/link";
import { DocumentUpload } from "@/domains/documents";

export default function DocumentUploadPage() {
  return (
    <main style={{ maxWidth: 1200, margin: "0 auto", padding: 32 }}>
      <Link href="/" style={{ color: "var(--muted)", display: "inline-block", marginBottom: 16 }}>
        ← 대시보드로 돌아가기
      </Link>
      <header style={{ marginBottom: 24 }}>
        <h1>계약서 업로드</h1>
        <p style={{ color: "var(--muted)" }}>
          웨딩홀, 스튜디오 등 계약서 파일을 업로드하면 AI가 내용을 분석합니다.
        </p>
      </header>
      <DocumentUpload />
    </main>
  );
}
