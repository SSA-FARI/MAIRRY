import { AuthGuard } from "@/domains/auth";
import { ContractEditPage } from "@/domains/contracts";

export default async function ContractEditRoute({
  params,
}: {
  params: Promise<{ contractId: string }>;
}) {
  const { contractId } = await params;
  return (
    <AuthGuard>
      <ContractEditPage contractId={contractId} />
    </AuthGuard>
  );
}
