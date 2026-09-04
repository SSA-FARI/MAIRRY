import { AuthGuard } from "@/domains/auth";
import { ContractReviewPage } from "@/domains/contracts";
import { AppHeader } from "@/shared/ui/app-header";

export default async function DocumentReviewRoute({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <AuthGuard>
      <div className="app-shell">
        <AppHeader active="documents" />
        <ContractReviewPage documentId={documentId} />
      </div>
    </AuthGuard>
  );
}
