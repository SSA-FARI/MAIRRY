import { AuthGuard } from "@/domains/auth";
import { ContractEditPage } from "@/domains/contracts";
import { AppHeader } from "@/shared/ui/app-header";

export default async function ContractEditRoute({
  params,
}: {
  params: Promise<{ contractId: string }>;
}) {
  const { contractId } = await params;
  return (
    <AuthGuard>
      <div className="app-shell">
        <AppHeader active="contracts" />
        <ContractEditPage contractId={contractId} />
      </div>
    </AuthGuard>
  );
}
