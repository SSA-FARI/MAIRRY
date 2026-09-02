import { AuthGuard } from "@/domains/auth";
import { ContractDetailPage } from "@/domains/contracts";

export default async function ContractDetailRoute({
  params,
}: {
  params: Promise<{ contractId: string }>;
}) {
  const { contractId } = await params;
  return (
    <AuthGuard>
      <ContractDetailPage contractId={contractId} />
    </AuthGuard>
  );
}
