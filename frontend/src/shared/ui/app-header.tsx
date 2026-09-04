import Link from "next/link";

const NAV_ITEMS = [
  { key: "dashboard", href: "/", label: "금융 대시보드" },
  { key: "contracts", href: "/contracts", label: "계약 관리" },
  { key: "documents", href: "/documents/upload", label: "계약서 업로드" },
  { key: "chat", href: "/chat", label: "AI 질문" },
] as const;

type NavigationKey = (typeof NAV_ITEMS)[number]["key"];

export function AppHeader({
  active,
  displayName,
}: {
  active: NavigationKey;
  displayName?: string;
}) {
  return (
    <header className="app-header">
      <Link className="app-logo" href="/" aria-label="MAIRRY 홈">
        MAIRRY
      </Link>
      <nav aria-label="주요 메뉴">
        {NAV_ITEMS.map((item) => {
          const isActive = item.key === active;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={isActive ? "active" : undefined}
              aria-current={isActive ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <span className="app-demo-badge">DEMO{displayName ? ` · ${displayName}` : ""}</span>
    </header>
  );
}
