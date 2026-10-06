import { useEffect, useState } from "react";
import { api, loadSession, saveSession, type Role, type Session } from "./api";
import CandidateApp from "./Candidate";
import EmployerApp from "./Employer";
import Validation from "./Validation";
import { Card, ErrorBox, GRADE_RU } from "./ui";

interface DemoAccount { key: string; role: Role; label: string; fsp_id: string | null; note: string }
interface DemoConfig { demo_mode: boolean; accounts: DemoAccount[] }
type Health = "checking" | "ok" | "unavailable";

export default function App() {
  const [session, setSession] = useState<Session | null>(() => loadSession());
  const [health, setHealth] = useState<Health>("checking");
  const [demo, setDemo] = useState<DemoConfig>({ demo_mode: false, accounts: [] });
  const [view, setView] = useState<"app" | "validation">("app");

  useEffect(() => {
    let cancelled = false;
    fetch("/health")
      .then((r) => r.json())
      .then((d: { status?: string }) => { if (!cancelled) setHealth(d.status === "ok" ? "ok" : "unavailable"); })
      .catch(() => { if (!cancelled) setHealth("unavailable"); });
    api<DemoConfig>("/api/demo/config").then((c) => { if (!cancelled) setDemo(c); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  const signIn = (s: Session | null) => { saveSession(s); setSession(s); setView("app"); };

  return (
    <div className="shell">
      <header className="top">
        <div className="brand"><span className="logo">FSP</span> Talent Market<span className="tag">обратный подбор по подтверждённым компетенциям</span></div>
        <div className="top-right">
          <span className={`health health-${health}`}>Backend: {health === "checking" ? "checking" : health === "ok" ? "ok" : "unavailable"}</span>
          <button className="link" onClick={() => setView(view === "validation" ? "app" : "validation")}>{view === "validation" ? "← Назад" : "Валидация"}</button>
          <a className="link" href="/docs" target="_blank" rel="noreferrer">API</a>
          {session && <><span className="who">{session.role === "candidate" ? "Кандидат" : "Работодатель"}</span><button onClick={() => signIn(null)}>Выйти</button></>}
        </div>
      </header>
      <main>
        {health === "unavailable" && <ErrorBox message="Backend недоступен. Проверьте, что сервис запущен (docker compose up)." />}
        {view === "validation" ? <Validation /> : !session ? <Login demo={demo} onSession={signIn} /> :
          session.role === "candidate" ? <CandidateApp session={session} demoMode={demo.demo_mode} /> : <EmployerApp session={session} />}
      </main>
    </div>
  );
}

function Login({ demo, onSession }: { demo: DemoConfig; onSession: (s: Session) => void }) {
  const [err, setErr] = useState("");
  const [mode, setMode] = useState<Role>("candidate");
  const [f, setF] = useState({ email: "", name: "", grade: "MIDDLE", company: "" });
  const enter = async (a: DemoAccount) => {
    setErr("");
    try {
      const r = await api<{ role: Role; id: number; access_token: string; fsp_id: string | null }>("/api/demo/login", { body: { account: a.key } });
      onSession({ role: r.role, token: r.access_token, id: r.id, fspId: r.fsp_id });
    } catch (e) { setErr((e as Error).message); }
  };
  const register = async () => {
    setErr("");
    try {
      if (mode === "candidate") {
        const r = await api<{ candidate_id: number; access_token: string }>("/api/candidates", { body: { email: f.email, full_name: f.name, claimed_grade: f.grade } });
        onSession({ role: "candidate", token: r.access_token, id: r.candidate_id });
      } else {
        const r = await api<{ employer_id: number; access_token: string }>("/api/employers", { body: { company_name: f.company, contact_email: f.email } });
        onSession({ role: "employer", token: r.access_token, id: r.employer_id });
      }
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="grid">
      <Card title="Мы не ранжируем резюме — мы подтверждаем компетенции">
        <ol className="steps">
          <li><b>Кандидат</b> заявляет специализацию и грейд, проходит параметризованный тест, получает Evidence Profile.</li>
          <li><b>Работодатель</b> описывает потребность и получает короткий объяснимый список: «Соответствие этой потребности», WHY и GAPS.</li>
          <li>Приглашение — <b>с обязательной зарплатой</b>. Контакты открываются <b>только после согласия</b> кандидата.</li>
        </ol>
        {err && <ErrorBox message={err} />}
        <h4>Регистрация</h4>
        <div className="row"><button className={mode === "candidate" ? "tab active" : "tab"} onClick={() => setMode("candidate")}>Я кандидат</button><button className={mode === "employer" ? "tab active" : "tab"} onClick={() => setMode("employer")}>Я работодатель</button></div>
        {mode === "candidate" ? <label>Имя<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label> : <label>Компания<input value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} /></label>}
        <label>Email<input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        {mode === "candidate" && <label>Целевой грейд<select value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value })}>{Object.entries(GRADE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>}
        <button className="primary" disabled={!f.email || (mode === "candidate" ? !f.name : !f.company)} onClick={register}>Создать аккаунт</button>
        <p className="muted">В MVP вход выдаётся при регистрации (без паролей); боевой путь — FSP ID / Keycloak.</p>
      </Card>
      <Card title="Демо-вход">
        {!demo.demo_mode ? <p className="muted">Демо-режим выключен (DEMO_MODE=false).</p> : (
          <ul className="accounts">{demo.accounts.map((a) => (
            <li key={a.key}><button onClick={() => enter(a)}>{a.label}</button><span className="muted">{a.note}</span></li>))}</ul>)}
        <p className="muted">Каноническая демонстрация: «Alexey Demo» → тест → Evidence Profile → подключить ФСП ID → «Demo Corp» → потребность → подбор → приглашение → принять.</p>
      </Card>
    </div>
  );
}
