import { AuthGuard } from "@/domains/auth";
import { ContractListPage } from "@/domains/contracts";

export default function ContractsRoute() {
  return (
    <AuthGuard>
      <ContractListPage />
    </AuthGuard>
  );
}
