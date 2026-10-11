import type { ReactNode } from "react";
import type { Contacts, Reason } from "./types";

export const GRADE_RU: Record<string, string> = { JUNIOR: "Junior", MIDDLE: "Middle", SENIOR: "Senior" };
export const COMPETENCY_RU: Record<string, string> = {
  python: "Python", sql: "SQL", api_fastapi: "API / FastAPI", testing: "Тестирование",
  docker_basics: "Основы Docker", system_thinking: "Системное мышление", postgresql: "PostgreSQL", kafka: "Kafka",
};
/** Русское название навыка/компетенции по коду; неизвестные коды показываем как есть. */
export const skillName = (code: string, fallback?: string): string => COMPETENCY_RU[code] ?? fallback ?? code;
/** В текстах причин код навыка стоит в начале строки («api_fastapi: …»): подменяем его на русское название. */
export const localizeReason = (r: { text: string; skill?: string | null }): string =>
  r.skill && r.text.startsWith(`${r.skill}:`) ? `${skillName(r.skill)}:${r.text.slice(r.skill.length + 1)}` : r.text;
const SUB_RU: Record<string, string> = { "1": "базовый", "2": "уверенный", "3": "сильный" };
/** «M2 · уверенный»: подуровень внутри грейда определяет только тест. */
export const subLabel = (s: string | null | undefined): string => (s ? `${s} · ${SUB_RU[s.slice(1)] ?? ""}` : "—");
/** Грейд + подуровень + специализация одной строкой: «Backend / Python · Middle (заявлено) · подтверждено Middle M2 · уверенный». */
export function gradeLine(c: { specialization?: string | null; claimed_grade: string | null; verified_grade: string | null; verified_sublevel: string | null }): string {
  const parts = [c.specialization ?? "Специализация не указана", `${c.claimed_grade ? GRADE_RU[c.claimed_grade] : "—"} (заявлено)`];
  if (c.verified_grade) parts.push(`подтверждено ${GRADE_RU[c.verified_grade]} ${subLabel(c.verified_sublevel)}`);
  return parts.join(" · ");
}
export const OPEN_INVITE = ["SENT", "VIEWED", "ACCEPTED", "CONTACTS_UNLOCKED"];
const INVITE_STATUS_RU: Record<string, string> = {
  SENT: "Приглашение отправлено", VIEWED: "Приглашение просмотрено", ACCEPTED: "Приглашение принято",
  CONTACTS_UNLOCKED: "Принято · контакты открыты", DECLINED: "Приглашение отклонено",
};
export function InviteBadge({ status }: { status?: string | null }) {
  if (!status) return <Badge tone="muted">приглашения нет</Badge>;
  return <Badge tone={status === "DECLINED" ? "bad" : status === "SENT" || status === "VIEWED" ? "info" : "ok"}>{INVITE_STATUS_RU[status] ?? status}</Badge>;
}
export const SALARY_TYPE_RU: Record<string, string> = { GROSS: "До налогов (GROSS)", NET: "На руки (NET)" };
export const FORMAT_RU: Record<string, string> = { REMOTE: "Удалённо", OFFICE: "Офис", HYBRID: "Гибрид" };
export const STATUS_RU: Record<string, string> = {
  SENT: "Отправлено",
  VIEWED: "Просмотрено",
  ACCEPTED: "Принято",
  CONTACTS_UNLOCKED: "Принято · контакты открыты",
  DECLINED: "Отклонено",
};

export function money(n: number): string {
  return n.toLocaleString("ru-RU").replace(/ /g, " ");
}
export function salaryRange(from: number, to: number, type: string): string {
  return `${money(from)}–${money(to)} ₽ · ${type}`;
}

export function Badge({ tone, children }: { tone: "ok" | "warn" | "bad" | "info" | "muted" | "brand"; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function VerificationBadge({ status }: { status: string }) {
  if (status === "VERIFIED") return <Badge tone="ok">✓ Подтверждено</Badge>;
  if (status === "NOT_VERIFIED") return <Badge tone="warn">Не подтверждено</Badge>;
  return <Badge tone="muted">Оценка не пройдена</Badge>;
}

export function Card({ title, children, aside }: { title?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="card">
      {(title || aside) && (
        <header className="card-head">
          <h3>{title}</h3>
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export function Loading({ what = "Загрузка" }: { what?: string }) {
  return <p className="muted" role="status">{what}…</p>;
}
export function ErrorBox({ message }: { message: string }) {
  return <p className="error" role="alert">⚠ {message}</p>;
}
export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

export function FitBlock({ label, fit, why, gaps }: { label: string; fit: number; why: Reason[]; gaps: Reason[] }) {
  const pct = Math.round(fit * 100);
  return (
    <div className="fit">
      <div className="fit-label">
        {label.startsWith("Соответствие") ? label.replace("Соответствие этой потребности", "Соответствие потребности") : `Соответствие потребности: ${pct}%`}
        <span className="fit-note"> — только к этой потребности, не общий рейтинг кандидата</span>
      </div>
      <div className="bar" aria-hidden="true">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="why-gaps">
        <div>
          <h4>Почему подходит</h4>
          {why.length === 0 && <p className="muted">Нет подтверждённых оснований</p>}
          <ul className="why">
            {why.map((r, i) => (
              <li key={`${r.code}-${i}`} title={r.code}>✓ {localizeReason(r)}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4>Пробелы</h4>
          {gaps.length === 0 && <p className="muted">Пробелов не обнаружено</p>}
          <ul className="gaps">
            {gaps.map((r, i) => (
              <li key={`${r.code}-${i}`} title={r.code}>△ {localizeReason(r)}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export function ContactBox({ unlocked, contacts }: { unlocked: boolean; contacts?: Contacts }) {
  if (!unlocked || !contacts) {
    return (
      <div className="contacts locked" data-testid="contacts-locked">
        🔒 Контакты скрыты. Они откроются только после того, как кандидат примет приглашение.
      </div>
    );
  }
  return (
    <div className="contacts unlocked" data-testid="contacts-unlocked">
      <strong>🔓 Контакты открыты по согласию кандидата</strong>
      <div>{contacts.full_name}</div>
      <div>{contacts.email}</div>
      <div>{contacts.phone ?? "телефон не указан"}</div>
    </div>
  );
}

export function SalaryBanner({ from, to, type }: { from: number; to: number; type: string }) {
  return (
    <div className="salary" data-testid="salary">
      <span className="salary-amount">{money(from)}–{money(to)} ₽</span>
      <span className="salary-type">{type === "GROSS" ? "GROSS · до вычета налога" : "NET · на руки"}</span>
    </div>
  );
}

export function Logo() {
  return <span className="brand"><span className="logo">FSP</span>Talent Market</span>;
}

const ICONS: Record<string, string> = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 4-6 8-6s8 2 8 6",
  check: "M12 22a10 10 0 110-20 10 10 0 010 20zM8 12l3 3 5-6",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4",
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  chat: "M4 5h16v11H9l-5 4z",
  search: "M11 18a7 7 0 110-14 7 7 0 010 14zM21 21l-5-5",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  chart: "M4 20V10M10 20V4M16 20v-8M22 20H2",
  gear: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12l2-1-1-3-2 .5-1.5-1.5.5-2-3-1-1 2h-2l-1-2-3 1 .5 2L6 7.5 4 7l-1 3 2 1v2l-2 1 1 3 2-.5L7.5 18l-.5 2 3 1 1-2h2l1 2 3-1-.5-2 1.5-1.5 2 .5 1-3-2-1z",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6L6 18",
  logout: "M9 4H5v16h4M16 8l4 4-4 4M20 12H9",
  plus: "M12 5v14M5 12h14",
  filter: "M3 5h18l-7 8v6l-4-2v-4z",
  download: "M12 4v11M7 11l5 5 5-5M5 20h14",
  book: "M5 4h10a3 3 0 013 3v13H8a3 3 0 01-3-3zM5 17a3 3 0 013-3h10",
};
export function Icon({ name, size = 18 }: { name: keyof typeof ICONS | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ flex: "none" }}>
      <path d={ICONS[name] ?? ICONS.list} />
    </svg>
  );
}

export function Kpi({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "mint" | "dark" }) {
  return (
    <div className={`kpi${tone ? ` ${tone}` : ""}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export function Avatar({ name }: { name: string }) {
  const parts = name.replace(/[^\p{L}\s]/gu, "").trim().split(/\s+/).filter(Boolean);
  const letters = (parts.length > 1 ? parts[0][0] + parts[1][0] : (parts[0] ?? "?").slice(0, 2)).toUpperCase();
  return <span className="avatar" aria-hidden="true">{letters}</span>;
}

export function PageHead({ title, sub, aside }: { title: string; sub?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{sub && <p>{sub}</p>}</div>
      {aside}
    </div>
  );
}
