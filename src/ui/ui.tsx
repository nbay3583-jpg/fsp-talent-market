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
