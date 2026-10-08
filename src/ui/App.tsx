import { useEffect, useRef, useState } from "react";
import { api, loadSession, saveSession, type Role, type Session } from "./api";
import CandidateApp from "./Candidate";
import EmployerApp from "./Employer";
import Validation from "./Validation";
import { Badge, Card, ErrorBox, GRADE_RU } from "./ui";

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
          {demo.demo_mode && <Badge tone="brand">Демо-режим</Badge>}
          <span className={`health health-${health}`}>{health === "checking" ? "Проверка системы…" : health === "ok" ? "Система работает" : "Система недоступна"}</span>
          <button className="link" onClick={() => setView(view === "validation" ? "app" : "validation")}>{view === "validation" ? "← Назад" : "Валидация"}</button>
          <a className="link" href="/docs" target="_blank" rel="noreferrer">API</a>
          {session && <><Badge tone="info">{session.role === "candidate" ? "Кандидат" : "Работодатель"}</Badge><button className="ghost" onClick={() => signIn(null)}>Выйти</button></>}
        </div>
      </header>
      <main>
        {health === "unavailable" && <ErrorBox message="Система недоступна. Проверьте, что сервис запущен (docker compose up)." />}
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
  const signup = useRef<HTMLDivElement>(null);
  const choose = (m: Role) => { setMode(m); signup.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }); };
  const parts = (a: DemoAccount) => {
    const m = /^(.*?)\s*\((.*)\)\s*$/.exec(a.label);
    return { name: m ? m[1] : a.label, hint: m ? m[2] : "" };
  };
  return (
    <div>
      <section className="hero">
        <Badge tone="brand">Обратный подбор для IT-специалистов</Badge>
        <h1>Мы не ранжируем резюме — мы подтверждаем компетенции</h1>
        <p className="lead">Кандидат проходит основную оценку компетенций, работодатель получает короткий объяснимый список с причинами выбора и пробелами. Контакты открываются только с согласия кандидата.</p>
        <div className="cta">
          <button className="primary large" onClick={() => choose("candidate")}>Я кандидат</button>
          <button className="large" onClick={() => choose("employer")}>Я работодатель</button>
        </div>
      </section>

      <h2 className="section-title">Как это работает</h2>
      <p className="section-sub">Три шага от заявки до осознанного контакта.</p>
      <ol className="steps">
        <li><b>Подтверждение компетенций</b>Кандидат указывает специализацию и желаемый грейд, проходит основную оценку компетенций и получает профиль подтверждённых компетенций.</li>
        <li><b>Объяснимый подбор</b>Работодатель описывает потребность и получает короткий объяснимый список кандидатов: соответствие потребности, причины выбора и пробелы.</li>
        <li><b>Приглашение с зарплатой</b>Каждое приглашение содержит зарплатную вилку. Контакты открываются только после согласия кандидата.</li>
      </ol>

      <h2 className="section-title">Демо-вход</h2>
      <p className="section-sub">Выберите готовую учётную запись — пароль не нужен.</p>
      {!demo.demo_mode ? <p className="empty">Демо-режим выключен.</p> : (
        <ul className="accounts">{demo.accounts.map((a) => {
          const { name, hint } = parts(a);
          return (
            <li key={a.key} className="account">
              <div className="badges">
                <Badge tone={a.role === "candidate" ? "info" : "brand"}>{a.role === "candidate" ? "Кандидат" : "Работодатель"}</Badge>
                {hint && <Badge tone="muted">{hint}</Badge>}
                {a.fsp_id && <Badge tone="info">ФСП</Badge>}
              </div>
              <h4>{name}</h4>
              <p>{a.note}</p>
              <button className="primary" onClick={() => enter(a)}>Войти как {name}</button>
            </li>);
        })}</ul>)}
      <div className="scenario"><h4>Сценарий демонстрации</h4><p>Основной сценарий: Алексей Демо → оценка компетенций → профиль подтверждённых компетенций → подключение ФСП ID → Демо-компания → потребность → подбор → приглашение → принятие → открытие контактов.</p></div>

      <h2 className="section-title">Регистрация</h2>
      <div className="signup" ref={signup}>
        <Card>
          {err && <ErrorBox message={err} />}
          <div className="row"><button className={mode === "candidate" ? "tab active" : "tab"} onClick={() => setMode("candidate")}>Я кандидат</button><button className={mode === "employer" ? "tab active" : "tab"} onClick={() => setMode("employer")}>Я работодатель</button></div>
          {mode === "candidate" ? <label>Имя<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label> : <label>Компания<input value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} /></label>}
          <label>Email<input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
          {mode === "candidate" && <label>Желаемый грейд<select value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value })}>{Object.entries(GRADE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>}
          <button className="primary" disabled={!f.email || (mode === "candidate" ? !f.name : !f.company)} onClick={register}>Создать аккаунт</button>
          <p className="muted">В демо вход выдаётся при регистрации (без паролей); в боевой версии вход будет через ФСП ID.</p>
        </Card>
      </div>
    </div>
  );
}
