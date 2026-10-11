import { useEffect, useRef, useState } from "react";
import { api, type Role } from "./api";

interface Answer { answer: string; topic: string | null; related: string[]; matched: boolean }
interface Msg { from: "me" | "bot"; text: string; topic?: string | null; related?: string[] }

const HELLO = "Здравствуйте! Я помощник по сайту: отвечаю по готовой базе знаний, без нейросетей. Выберите вопрос или напишите свой.";

export default function Assistant({ role }: { role?: Role | null }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [hints, setHints] = useState<string[]>([]);
  const [msgs, setMsgs] = useState<Msg[]>([{ from: "bot", text: HELLO }]);
  const logRef = useRef<HTMLDivElement>(null);

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

  if (!open) return <button className="assistant-fab" aria-label="Открыть помощника" onClick={() => setOpen(true)}>? Помощник</button>;
  return (
    <aside className="assistant" aria-label="Помощник по сайту">
      <div className="assistant-head"><strong>Помощник</strong><button className="link" aria-label="Закрыть помощника" onClick={() => setOpen(false)}>✕</button></div>
      <div className="assistant-log" role="log" aria-live="polite" ref={logRef}>
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.from}`}>
            {m.topic && <div className="muted">{m.topic}</div>}
            {m.text}
            {m.related && m.related.length > 0 && <div className="muted">Смотрите также: {m.related.join(" · ")}</div>}
          </div>
        ))}
      </div>
      <div className="assistant-hints">
        {hints.map((h) => <button key={h} className="chip" onClick={() => send(h)}>{h}</button>)}
      </div>
      <form className="assistant-form" onSubmit={(e) => { e.preventDefault(); void send(text); }}>
        <input value={text} maxLength={300} placeholder="Ваш вопрос" aria-label="Вопрос помощнику" onChange={(e) => setText(e.target.value)} />
        <button className="primary" disabled={busy || text.trim().length < 2}>Спросить</button>
      </form>
    </aside>
  );
}
