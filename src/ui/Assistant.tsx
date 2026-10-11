import { useEffect, useId, useRef, useState } from "react";
import { api, type Role } from "./api";
import { useAssistantPage } from "./assistantContext";
import { Icon } from "./ui";

interface Answer { answer: string; topic: string | null; related: string[]; matched: boolean }
interface Msg { from: "me" | "bot"; text: string; topic?: string | null; related?: string[] }

const HELLO = "Здравствуйте! Я отвечаю по готовой базе знаний сайта, без нейросетей. Выберите вопрос или напишите свой.";

/** Page-specific quick questions; each is answered by the same knowledge base via /api/assistant/ask. */
const PAGE_HINTS: Record<string, { title: string; hints: string[] }> = {
  "candidate:test": { title: "Оценка навыков", hints: ["Как проходит оценка?", "Что если не прошёл оценку?", "Что значат подуровни J1–S3?"] },
  "candidate:evidence": { title: "Профиль компетенций", hints: ["Что значат подуровни J1–S3?", "Как учитывается история ФСП?", "Что видит работодатель в моём профиле?"] },
  "candidate:fit": { title: "Рекомендации", hints: ["Как формируются рекомендации?", "Как указать зарплату GROSS или NET?", "Что видит работодатель в моём профиле?"] },
  "candidate:invitations": { title: "Приглашения", hints: ["Как принять или отклонить приглашение?", "Когда открываются мои контакты?", "Что видит работодатель в моём профиле?"] },
  "candidate:profile": { title: "Настройки профиля", hints: ["Как скрыть профиль из поиска?", "Как указать зарплату GROSS или NET?", "Что видит работодатель в моём профиле?"] },
  "candidate:overview": { title: "Обзор", hints: ["Как проходит оценка?", "Когда открываются мои контакты?", "Что такое FSP Talent Market?"] },
  "employer:match": { title: "Подбор по потребности", hints: ["Как создать потребность?", "Что значит «соответствие этой потребности»?", "Как работает совместимость с командой?"] },
  "employer:pool": { title: "Поиск кандидатов", hints: ["Что значит «соответствие этой потребности»?", "Что значат подуровни J1–S3?", "Что видит работодатель в профиле кандидата?"] },
  "employer:fit": { title: "Избранное", hints: ["Как работает избранное?", "Как работают рекомендации?", "Когда открываются контакты кандидата?"] },
  "employer:team": { title: "Команда", hints: ["Как работает совместимость с командой?", "Что значит «соответствие этой потребности»?", "Как создать потребность?"] },
  "employer:invitations": { title: "Приглашения", hints: ["Когда открываются контакты кандидата?", "Как создать потребность?", "Что видит работодатель в профиле кандидата?"] },
};

export default function Assistant({ role }: { role?: Role | null }) {
  const page = useAssistantPage();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [hints, setHints] = useState<string[]>([]);
  const [msgs, setMsgs] = useState<Msg[]>([{ from: "bot", text: HELLO }]);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fabRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const titleId = useId();

  const ctx = role && page ? PAGE_HINTS[`${role}:${page}`] : undefined;

  useEffect(() => {  // scroll only the message area (not the page) to the newest message
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, busy, open]);

  useEffect(() => {
    if (!open) return;
    api<{ suggestions: string[] }>(`/api/assistant/suggestions${role ? `?role=${role}` : ""}`)
      .then((r) => setHints(r.suggestions))
      .catch(() => setHints([]));
  }, [open, role]);

  useEffect(() => {  // focus: into the field on open, back to the launcher on close
    if (open) inputRef.current?.focus();
    else if (wasOpen.current) fabRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const send = async (q: string) => {
    const question = q.trim();
    if (question.length < 2 || busy) return;
    setText("");
    setBusy(true);
    setMsgs((m) => [...m, { from: "me", text: question }]);
    try {
      const r = await api<Answer>("/api/assistant/ask", { body: { question, role: role ?? null } });
      setMsgs((m) => [...m, { from: "bot", text: r.answer, topic: r.topic, related: r.related }]);
    } catch {
      setMsgs((m) => [...m, { from: "bot", text: "Помощник временно недоступен. Основная функциональность сайта работает." }]);
    } finally {
      setBusy(false);
    }
  };

  const shown = ctx ? ctx.hints : hints;
  const asked = new Set(msgs.filter((m) => m.from === "me").map((m) => m.text));
  const quick = shown.filter((h) => !asked.has(h));

  return (
    <>
      <button ref={fabRef} className={`assistant-fab${open ? " hidden" : ""}`} aria-label="Открыть помощника" aria-expanded={open} aria-haspopup="dialog" tabIndex={open ? -1 : 0} onClick={() => setOpen(true)}>
        <Icon name="assistant" size={22} /><span className="assistant-fab-text">Помощник</span>
      </button>
      {open && (
        <aside className="assistant" role="dialog" aria-labelledby={titleId}>
          <header className="assistant-head">
            <span className="assistant-avatar" aria-hidden="true"><Icon name="assistant" size={20} /></span>
            <div className="assistant-title">
              <strong id={titleId}>Помощник</strong>
              <span>Ответы из базы знаний сайта · без нейросетей</span>
            </div>
            <button className="icon-btn" aria-label="Закрыть помощника" onClick={() => setOpen(false)}><Icon name="close" size={18} /></button>
          </header>
          <div className="assistant-log" role="log" aria-live="polite" aria-label="История диалога" ref={logRef}>
            {msgs.map((m, i) => (
              <div key={i} className={`bubble ${m.from}`}>
                {m.topic && <div className="bubble-topic">{m.topic}</div>}
                {m.text}
                {m.related && m.related.length > 0 && <div className="bubble-related">Смотрите также: {m.related.join(" · ")}</div>}
              </div>
            ))}
            {busy && <div className="bubble bot muted" aria-live="polite">Ищу в базе знаний…</div>}
          </div>
          {quick.length > 0 && (
            <div className="assistant-hints-wrap">
              <div className="assistant-hints-label">{ctx ? `Частые вопросы · ${ctx.title}` : "Частые вопросы"}</div>
              <div className="assistant-hints">
                {quick.map((h) => <button key={h} className="chip" disabled={busy} onClick={() => void send(h)}>{h}</button>)}
              </div>
            </div>
          )}
          <form className="assistant-form" onSubmit={(e) => { e.preventDefault(); void send(text); }}>
            <input ref={inputRef} value={text} maxLength={300} placeholder="Напишите вопрос" aria-label="Вопрос помощнику" onChange={(e) => setText(e.target.value)} />
            <button className="primary" disabled={busy || text.trim().length < 2}>Спросить</button>
          </form>
        </aside>
      )}
    </>
  );
}
