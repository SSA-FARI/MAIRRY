"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { DemoSession, DemoUser } from "./types";

export const DEMO_SESSION_STORAGE_KEY = "mairry.demo-session";

interface DemoSessionContextValue {
  isReady: boolean;
  session: DemoSession | null;
  startSession: (session: DemoSession) => void;
}

const DemoSessionContext = createContext<DemoSessionContextValue | undefined>(undefined);

export function DemoSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<DemoSession | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const storedSession = window.sessionStorage.getItem(DEMO_SESSION_STORAGE_KEY);

    if (storedSession !== null) {
      try {
        setSession(parseDemoSession(JSON.parse(storedSession) as unknown));
      } catch {
        window.sessionStorage.removeItem(DEMO_SESSION_STORAGE_KEY);
      }
    }

    setIsReady(true);
  }, []);

  const startSession = useCallback((nextSession: DemoSession) => {
    // This public profile only preserves demo UX across reloads; it is not authentication.
    const safeSession: DemoSession = {
      mode: "DEMO",
      user: {
        id: nextSession.user.id,
        loginId: nextSession.user.loginId,
        displayName: nextSession.user.displayName,
        email: nextSession.user.email,
      },
    };

    window.sessionStorage.setItem(DEMO_SESSION_STORAGE_KEY, JSON.stringify(safeSession));
    setSession(safeSession);
  }, []);

  const value = useMemo(
    () => ({ isReady, session, startSession }),
    [isReady, session, startSession],
  );

  return <DemoSessionContext.Provider value={value}>{children}</DemoSessionContext.Provider>;
}

export function useDemoSession(): DemoSessionContextValue {
  const context = useContext(DemoSessionContext);

  if (context === undefined) {
    throw new Error("useDemoSession must be used within DemoSessionProvider");
  }

  return context;
}

function parseDemoSession(value: unknown): DemoSession | null {
  if (!isRecord(value) || value.mode !== "DEMO" || !isDemoUser(value.user)) {
    return null;
  }

  return {
    mode: "DEMO",
    user: {
      id: value.user.id,
      loginId: value.user.loginId,
      displayName: value.user.displayName,
      email: value.user.email,
    },
  };
}

function isDemoUser(value: unknown): value is DemoUser {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.loginId === "string" &&
    typeof value.displayName === "string" &&
    (typeof value.email === "string" || value.email === null)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
