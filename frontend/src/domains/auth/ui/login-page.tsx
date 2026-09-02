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
      <div className="login-shell">
        <section className="login-introduction" aria-labelledby="login-title">
          <p className="login-eyebrow">MAIRRY</p>
          <span className="login-kicker">WEDDING FINANCE PLANNER</span>
          <h1 id="login-title">우리의 결혼 준비를 한곳에서</h1>
          <p className="login-description">
            계약부터 지급 일정, 남은 결혼 자금까지 정확하고 차분하게 관리하세요.
          </p>
          <ul className="login-features" aria-label="주요 기능">
            <li>
              <span aria-hidden="true">01</span>
              <div>
                <strong>자금 현황</strong>
                <small>총자산과 남은 지출을 한눈에 확인</small>
              </div>
            </li>
            <li>
              <span aria-hidden="true">02</span>
              <div>
                <strong>지급 일정</strong>
                <small>계약별 지급일을 월간 캘린더로 관리</small>
              </div>
            </li>
            <li>
              <span aria-hidden="true">03</span>
              <div>
                <strong>지출 시뮬레이션</strong>
                <small>추가 비용 이후의 예상 잔액 확인</small>
              </div>
            </li>
          </ul>
          <p className="login-trust-note">계약 데이터에 근거한 결혼 자금 플래닝</p>
        </section>

        <section className="login-card" aria-labelledby="demo-login-title">
          <div className="login-brand" aria-hidden="true">
            M
          </div>
          <span className="login-demo-badge">DEMO</span>
          <h2 id="demo-login-title">금융 대시보드 체험하기</h2>
          <p>준비된 데모 계정으로 MAIRRY의 핵심 기능을 바로 확인할 수 있습니다.</p>

          <div className="login-demo-note">
            <strong>Demo Mode</strong>
            <span>회원가입이나 개인정보 입력 없이 안전하게 둘러보세요.</span>
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
          <small className="login-security-note">
            로그인 정보는 현재 브라우저 세션에만 유지됩니다.
          </small>
        </section>
      </div>
    </main>
  );
}
