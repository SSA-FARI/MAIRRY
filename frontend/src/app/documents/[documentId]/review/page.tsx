import { AuthGuard } from "@/domains/auth";
import { ContractReviewPage } from "@/domains/contracts";

export default async function DocumentReviewRoute({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <AuthGuard>
      <ContractReviewPage documentId={documentId} />
    </AuthGuard>
  );
}
