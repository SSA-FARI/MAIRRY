import Link from "next/link";
import { DocumentUploadFlow } from "@/domains/documents";
import { AuthGuard } from "@/domains/auth";
import { AppHeader } from "@/shared/ui/app-header";

export default function DocumentUploadPage() {
  return (
    <AuthGuard>
      <div className="app-shell">
        <AppHeader active="documents" />
        <main className="content-page">
          <nav className="page-nav" aria-label="계약서 업로드 화면 탐색">
            <Link href="/">대시보드</Link>
            <span aria-hidden="true">/</span>
            <span>계약서 업로드</span>
          </nav>
          <header className="page-header">
            <p className="eyebrow">DOCUMENT UPLOAD</p>
            <h1>계약서 업로드</h1>
            <p>웨딩홀, 스튜디오 등 계약서 파일을 업로드하면 AI가 내용을 분석합니다.</p>
          </header>
          <DocumentUploadFlow />
        </main>
      </div>
    </AuthGuard>
  );
}
