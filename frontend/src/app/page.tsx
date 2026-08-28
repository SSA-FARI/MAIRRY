import { AuthGuard } from "@/domains/auth";
import { DashboardPage } from "@/domains/finance";

export default function HomePage() {
  return (
    <AuthGuard>
      <DashboardPage />
    </AuthGuard>
  );
}
