"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { demoLogin } from "../api/demo-login-api";
import { useDemoSession } from "../model/auth-context";

const LOGIN_ERROR_MESSAGE = "데모 계정으로 로그인하지 못했어요. 잠시 후 다시 시도해 주세요.";

export function LoginPage() {
  const router = useRouter();
  const { isReady, session, startSession } = useDemoSession();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const requestInFlight = useRef(false);

  useEffect(() => {
    if (isReady && session !== null) {
      router.replace("/");
    }
  }, [isReady, router, session]);

  async function handleDemoLogin() {
    if (requestInFlight.current || session !== null) {
      return;
    }

    requestInFlight.current = true;
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const nextSession = await demoLogin();
      startSession(nextSession);
    } catch {
      setErrorMessage(LOGIN_ERROR_MESSAGE);
    } finally {
      requestInFlight.current = false;
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand" aria-hidden="true">
          M
        </div>
        <p className="login-eyebrow">MAIRRY</p>
        <h1 id="login-title">우리의 결혼 준비를 한곳에서</h1>
        <p className="login-description">
          계약과 지급 일정을 차분하게 정리하고, 남은 결혼 자금을 한눈에 확인해 보세요.
        </p>

        <div className="login-demo-note">
          <strong>Demo Mode</strong>
          <span>별도의 회원가입 없이 데모 계정으로 서비스를 체험할 수 있어요.</span>
        </div>

        <button
          className="login-button"
          type="button"
          onClick={handleDemoLogin}
          disabled={!isReady || isSubmitting || session !== null}
          aria-busy={isSubmitting}
        >
          {isSubmitting ? (
            <>
              <span className="login-spinner" aria-hidden="true" />
              로그인 중...
            </>
          ) : (
            "데모 계정으로 시작하기"
          )}
        </button>

        {errorMessage !== null && (
          <p className="login-error" role="alert">
            {errorMessage}
          </p>
        )}
      </section>
    </main>
  );
}
