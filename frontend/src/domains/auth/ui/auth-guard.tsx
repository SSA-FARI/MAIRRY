"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useDemoSession } from "../model/auth-context";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isReady, session } = useDemoSession();

  useEffect(() => {
    if (isReady && session === null) {
      router.replace("/login");
    }
  }, [isReady, router, session]);

  if (!isReady || session === null) {
    return (
      <main className="route-loading" aria-live="polite">
        화면을 준비하고 있어요...
      </main>
    );
  }

  return children;
}
