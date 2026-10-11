import { useEffect, useRef, useState } from "react";
import { api, loadSession, saveSession, type Role, type Session } from "./api";
import CandidateApp from "./Candidate";
import EmployerApp from "./Employer";
import Assistant from "./Assistant";
import Validation from "./Validation";
import { TeamSurvey } from "./TeamFit";
import type { Catalog } from "./types";
import { Avatar, Badge, Card, ErrorBox, GRADE_RU, Icon, Logo, skillName } from "./ui";

interface DemoAccount { key: string; role: Role; label: string; fsp_id: string | null; note: string }
interface DemoConfig { demo_mode: boolean; accounts: DemoAccount[] }
export type Health = "checking" | "ok" | "unavailable";
interface Facts {
  candidates?: number; needs?: number; methods?: number; sublevels?: number; skills?: Catalog["skills"];
  matching?: { name: string; p5: number; ours: boolean }[];
}
const HEALTH_RU: Record<Health, string> = { checking: "Проверка системы…", ok: "Система работает", unavailable: "Система недоступна" };
const METHOD_RU: Record<string, string> = { keyword_baseline: "Ключевые слова", hard_filters_only: "Только ограничения", evidence_matching: "Подбор по подтверждениям" };

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

  const [notice, setNotice] = useState("");
  useEffect(() => {  // link from the confirmation email: /?verify_email=<token>
    const token = new URLSearchParams(window.location.search).get("verify_email");
    if (!token) return;
    api("/api/auth/verify-email", { body: { token } })
      .then(() => setNotice("Email подтверждён. Профиль виден работодателям, пока включена видимость в настройках."))
      .catch(() => setNotice("Ссылка подтверждения недействительна или устарела. Запросите новую в профиле."))
      .finally(() => window.history.replaceState(null, "", window.location.pathname));
  }, []);

  useEffect(() => {
    const onExpired = () => { saveSession(null); setSession(null); setNotice("Сессия истекла. Войдите снова."); };
    window.addEventListener("fsp:unauthorized", onExpired);
    return () => window.removeEventListener("fsp:unauthorized", onExpired);
  }, []);

  const surveyToken = new URLSearchParams(window.location.search).get("team_survey");
  const signIn = (s: Session | null) => { saveSession(s); setSession(s); setView("app"); };

  const banners = (
    <>
      {notice && <p className="notice" role="status">{notice}</p>}
      {health === "unavailable" && <ErrorBox message="Система недоступна. Проверьте, что сервис запущен (docker compose up)." />}
    </>
  );

  if (session && !surveyToken && view === "app") {
    const shell = { health, demoMode: demo.demo_mode, onLogout: () => signIn(null), onValidation: () => setView("validation"), banners };
    return (
      <>
        {session.role === "candidate" ? <CandidateApp session={session} shell={shell} /> : <EmployerApp session={session} shell={shell} />}
        <Assistant role={session.role} />
      </>
    );
  }

  return (
    <div className="public">
      <header className="topbar">
        <Logo />
        {!surveyToken && view === "app" && (
          <nav aria-label="Разделы">
            <a href="#for-candidates">Для кандидатов</a>
            <a href="#for-employers">Для работодателей</a>
            <a href="#how">Как это работает</a>
            <button onClick={() => setView("validation")}>Валидация</button>
          </nav>
        )}
        <div className="topbar-actions" style={surveyToken || view !== "app" ? { marginLeft: "auto" } : undefined}>
          <span className={`health health-${health}`}>{HEALTH_RU[health]}</span>
          {view === "validation" && <button onClick={() => setView("app")}>{session ? "← В кабинет" : "← На главную"}</button>}
          {view === "app" && !surveyToken && <button className="primary" onClick={() => document.getElementById("auth")?.scrollIntoView?.({ behavior: "smooth" })}>Войти</button>}
        </div>
      </header>
      <main>
        {banners}
        {surveyToken ? <TeamSurvey token={surveyToken} /> : view === "validation" ? <Validation /> : <Landing demo={demo} onSession={signIn} />}
      </main>
      <Assistant role={session?.role ?? null} />
    </div>
  );
}

function Landing({ demo, onSession }: { demo: DemoConfig; onSession: (s: Session) => void }) {
  const [facts, setFacts] = useState<Facts>({});
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [role, setRole] = useState<Role>("candidate");
  const authRef = useRef<HTMLDivElement>(null);

  useEffect(() => {  // only real numbers: validation artifact + catalog
    let off = false;
    api<{ dataset: { candidates: number; needs: number }; matching: Record<string, Record<string, number>> }>("/api/validation/summary")
      .then((s) => {
        if (off) return;
        const matching = Object.entries(METHOD_RU).filter(([k]) => s.matching[k]).map(([k, name]) => ({ name, p5: s.matching[k]["p@5"], ours: k === "evidence_matching" }));
        setFacts((f) => ({ ...f, candidates: s.dataset.candidates, needs: s.dataset.needs, methods: Object.keys(s.matching).length, matching }));
      }).catch(() => undefined);
    api<Catalog>("/api/catalog")
      .then((c) => { if (!off) setFacts((f) => ({ ...f, skills: c.skills, sublevels: Object.values(c.grades).flat().length })); })
      .catch(() => undefined);
    return () => { off = true; };
  }, []);

  const go = (r: Role, m: "login" | "register") => {
    setRole(r); setAuthMode(m);
    authRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };
  const stats: [string, string][] = [];
  if (facts.sublevels) stats.push([`J1–S3`, `${facts.sublevels} подуровней грейда`]);
  if (facts.skills) stats.push([String(facts.skills.length), "навыков в каталоге"]);
  if (facts.candidates !== undefined) stats.push([String(facts.candidates), "кандидатов в валидации"]);
  if (facts.methods) stats.push([String(facts.methods), "метода подбора в сравнении"]);

  return (
    <div>
      <section className="hero">
        <div>
          <span className="hero-eyebrow">Обратный подбор для IT-специалистов</span>
          <h1>Подтверждённые навыки <em>открывают больше возможностей</em></h1>
          <p className="lead">Кандидат проходит основную оценку компетенций и получает подтверждённый грейд. Работодатель видит короткий объяснимый список: почему кандидат подходит и какие пробелы есть. Контакты открываются только с согласия кандидата.</p>
          <div className="cta">
            <button className="primary large" onClick={() => go("candidate", "register")}>Я кандидат →<small>Проверить свои навыки</small></button>
            <button className="large" onClick={() => go("employer", "register")}>Я работодатель →<small>Найти проверенных специалистов</small></button>
          </div>
          {stats.length > 0 && <div className="hero-stats">{stats.map(([v, l]) => <div key={l}><b>{v}</b><span>{l}</span></div>)}</div>}
        </div>
        <Showcase facts={facts} />
      </section>

      <div className="grid-2" style={{ marginTop: 8 }}>
        <Card title="Кандидату">
          <p id="for-candidates" style={{ marginTop: 0 }}>Подтвердите грейд J1–S3 основной оценкой компетенций и покажите работодателям то, что проверено, а не только заявлено.</p>
          <button className="primary" onClick={() => go("candidate", "register")}>Проверить свои навыки →</button>
        </Card>
        <Card title="Работодателю">
          <p id="for-employers" style={{ marginTop: 0 }}>Опишите потребность и получите короткий список с процентом соответствия требованиям, причинами выбора и пробелами. Экспорт CSV/JSON — без контактов.</p>
          <button onClick={() => go("employer", "register")}>Найти проверенных специалистов →</button>
        </Card>
      </div>

      <h2 className="section-title" id="how">Как это работает</h2>
      <p className="section-sub">Три шага от заявки до осознанного контакта.</p>
      <ol className="steps">
        <li><b>Подтверждение компетенций</b>Кандидат указывает специализацию и желаемый грейд, проходит основную оценку компетенций и получает профиль подтверждённых компетенций.</li>
        <li><b>Объяснимый подбор</b>Работодатель описывает потребность и получает короткий список: соответствие требованиям, причины выбора и пробелы.</li>
        <li><b>Приглашение с зарплатой</b>Каждое приглашение содержит зарплатную вилку. Контакты открываются только после согласия кандидата.</li>
      </ol>

      <h2 className="section-title">Вход и регистрация</h2>
      <p className="section-sub">Создайте аккаунт или откройте готовый демо-аккаунт без пароля.</p>
      <div className="auth" id="auth" ref={authRef}>
        <AuthCard mode={authMode} setMode={setAuthMode} role={role} setRole={setRole} demoMode={demo.demo_mode} onSession={onSession} />
        <DemoPanel demo={demo} onSession={onSession} />
      </div>

      <footer className="footer">
        <span>FSP Talent Market — MVP конкурсного проекта</span>
        <span>Подбор детерминирован, без нейросетей</span>
        <a href="/docs" target="_blank" rel="noreferrer">API-документация</a>
      </footer>
    </div>
  );
}

/** Right-hand hero card: built only from the real catalog and the real validation artifact. */
function Showcase({ facts }: { facts: Facts }) {
  const skills = facts.skills?.slice(0, 6);
  const max = facts.matching ? Math.max(...facts.matching.map((m) => m.p5), 0.0001) : 1;
  return (
    <aside className="showcase" aria-label="Что получает кандидат и работодатель">
      <div className="showcase-head">
        <span className="company-mark"><Icon name="shield" size={18} /></span>
        <div>
          <h3>Профиль подтверждённых навыков</h3>
          <div className="sub">Каждый навык помечен: подтверждён оценкой или только заявлен</div>
        </div>
      </div>
      <div>
        {skills ? skills.map((s) => (
          <div className="showcase-skill" key={s.code} style={{ marginBottom: 6 }}>
            <span className={`tick${s.verifiable ? "" : " no"}`}>{s.verifiable ? "✓" : "–"}</span>
            {skillName(s.code, s.name)}
            <small>{s.verifiable ? "подтверждается оценкой" : "только опыт"}</small>
          </div>
        )) : <p className="muted">Каталог навыков загружается…</p>}
      </div>
      <div>
        <h3>Подбор по подтверждениям</h3>
        <p className="muted" style={{ margin: "2px 0 8px" }}>Точность в топ-5 (P@5) на фиксированном наборе валидации.</p>
        {facts.matching ? facts.matching.map((m) => (
          <div key={m.name} className={`mbar${m.ours ? " hl" : ""}`}>
            <span>{m.name}</span>
            <span className="track"><span style={{ width: `${(m.p5 / max) * 100}%` }} /></span>
            <b>{m.p5.toFixed(2)}</b>
          </div>
        )) : <p className="muted">Результаты валидации недоступны.</p>}
      </div>
      <div className="row" style={{ gap: 8 }}>
        <Badge tone="ok">Почему подходит</Badge><Badge tone="warn">Пробелы</Badge><Badge tone="muted">Контакты скрыты</Badge>
      </div>
    </aside>
  );
}

type Step = "password" | "code" | "verify";

/** One compact auth interface: Войти / Регистрация, with role switch. */
function AuthCard({ mode, setMode, role, setRole, demoMode, onSession }: {
  mode: "login" | "register"; setMode: (m: "login" | "register") => void; role: Role; setRole: (r: Role) => void; demoMode: boolean; onSession: (s: Session) => void;
}) {
  const [step, setStep] = useState<Step>("password");
  const [f, setF] = useState({ email: "", password: "", code: "", newPassword: "", name: "", company: "", grade: "MIDDLE" });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  type Out = { role: Role; id: number; access_token: string };
  const done = (r: Out) => onSession({ role: r.role, token: r.access_token, id: r.id });
  const wrap = async (fn: () => Promise<void>) => { setErr(""); try { await fn(); } catch (e) { setErr((e as Error).message === "invalid credentials" ? "Неверный email или пароль." : (e as Error).message); } };
  const login = () => wrap(async () => done(await api<Out>("/api/auth/login", { body: { role, email: f.email, password: f.password } })));
  const request = () => wrap(async () => {
    const r = await api<{ demo_code?: string }>("/api/auth/code/request", { body: { role, email: f.email } });
    setMsg(r.demo_code ? `Демо-режим: почта не настроена, код ${r.demo_code}` : "Если такой аккаунт есть, мы отправили код на email. Он действует 15 минут.");
    setStep("verify");
  });
  const verify = () => wrap(async () => done(await api<Out>("/api/auth/code/verify", { body: { role, email: f.email, code: f.code, ...(f.newPassword ? { new_password: f.newPassword } : {}) } })));
  const register = () => wrap(async () => {
    if (role === "candidate") {
      const r = await api<{ candidate_id: number; access_token: string; demo_verification_link?: string }>("/api/candidates", { body: { email: f.email, full_name: f.name, claimed_grade: f.grade, password: f.password } });
      try { if (r.demo_verification_link) sessionStorage.setItem("fsp.demo_verify", r.demo_verification_link); } catch { /* storage unavailable */ }
      onSession({ role: "candidate", token: r.access_token, id: r.candidate_id });
    } else {
      const r = await api<{ employer_id: number; access_token: string }>("/api/employers", { body: { company_name: f.company, contact_email: f.email, password: f.password } });
      onSession({ role: "employer", token: r.access_token, id: r.employer_id });
    }
  });
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });
  const canRegister = !!f.email && f.password.length >= 8 && (role === "candidate" ? !!f.name : !!f.company);
  const onEnter = (e: React.KeyboardEvent<HTMLDivElement>) => {  // Enter in a field submits the visible primary action
    if (e.key !== "Enter" || (e.target as HTMLElement).tagName !== "INPUT") return;
    e.preventDefault();
    if (mode === "register") { if (canRegister) void register(); }
    else if (step === "password") { if (f.email && f.password) void login(); }
    else if (f.code.length === 6 && (!f.newPassword || f.newPassword.length >= 8)) void verify();
  };
  return (
    <div className="auth-card" onKeyDown={onEnter}>
      <h2>{mode === "login" ? "Вход в аккаунт" : "Создать аккаунт"}</h2>
      <div className="seg full" role="tablist" aria-label="Режим">
        <button role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setErr(""); }}>Войти</button>
        <button role="tab" aria-selected={mode === "register"} className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setErr(""); setStep("password"); }}>Регистрация</button>
      </div>
      <div className="seg full" role="tablist" aria-label="Роль">
        <button role="tab" aria-selected={role === "candidate"} className={role === "candidate" ? "active" : ""} onClick={() => setRole("candidate")}>Кандидат</button>
        <button role="tab" aria-selected={role === "employer"} className={role === "employer" ? "active" : ""} onClick={() => setRole("employer")}>Работодатель</button>
      </div>
      {err && <div style={{ marginTop: 12 }}><ErrorBox message={err} /></div>}

      {mode === "register" ? (
        <>
          {role === "candidate"
            ? <label>Имя<input autoComplete="name" value={f.name} onChange={(e) => set("name", e.target.value)} /></label>
            : <label>Компания<input autoComplete="organization" value={f.company} onChange={(e) => set("company", e.target.value)} /></label>}
          <label>Email<input type="email" autoComplete="username" value={f.email} onChange={(e) => set("email", e.target.value)} /></label>
          {role === "candidate" && <label>Желаемый грейд<select value={f.grade} onChange={(e) => set("grade", e.target.value)}>{Object.entries(GRADE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>}
          <label>Пароль (не короче 8 символов)<input type="password" autoComplete="new-password" value={f.password} onChange={(e) => set("password", e.target.value)} /></label>
          <button className="primary large" style={{ width: "100%" }} disabled={!f.email || f.password.length < 8 || (role === "candidate" ? !f.name : !f.company)} onClick={register}>Создать аккаунт</button>
          <p className="muted" style={{ marginBottom: 0 }}>Позже можно войти по email и паролю или по одноразовому коду из письма.</p>
        </>
      ) : (
        <>
          <label>Email<input type="email" autoComplete="username" value={f.email} onChange={(e) => set("email", e.target.value)} /></label>
          {step === "password" ? (
            <>
              <label>Пароль<input type="password" autoComplete="current-password" value={f.password} onChange={(e) => set("password", e.target.value)} /></label>
              <button className="primary large" style={{ width: "100%" }} disabled={!f.email || !f.password} onClick={login}>Войти</button>
              <p style={{ margin: "10px 0 0" }}><button className="link" disabled={!f.email} onClick={request}>Войти по коду из письма / забыли пароль</button></p>
            </>
          ) : (
            <>
              {msg && <p className="muted" role="status">{msg}</p>}
              <label>Код из письма<input inputMode="numeric" maxLength={6} value={f.code} onChange={(e) => set("code", e.target.value.replace(/\D/g, ""))} /></label>
              <label>Новый пароль (необязательно, не короче 8 символов)<input type="password" autoComplete="new-password" value={f.newPassword} onChange={(e) => set("newPassword", e.target.value)} /></label>
              <button className="primary large" style={{ width: "100%" }} disabled={f.code.length !== 6 || (!!f.newPassword && f.newPassword.length < 8)} onClick={verify}>Подтвердить и войти</button>
              <p style={{ margin: "10px 0 0" }}><button className="link" onClick={() => { setStep("password"); setMsg(""); }}>← Вход по паролю</button></p>
            </>
          )}
          {demoMode && <p className="muted" style={{ marginBottom: 0 }}>Нет аккаунта? Выберите демо-аккаунт справа — пароль не нужен.</p>}
        </>
      )}
    </div>
  );
}

const FEATURED = "candidate_verified";

function DemoPanel({ demo, onSession }: { demo: DemoConfig; onSession: (s: Session) => void }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const enter = async (a: DemoAccount) => {
    setErr(""); setBusy(a.key);
    try {
      const r = await api<{ role: Role; id: number; access_token: string; fsp_id: string | null }>("/api/demo/login", { body: { account: a.key } });
      onSession({ role: r.role, token: r.access_token, id: r.id, fspId: r.fsp_id, demo: true });
    } catch (e) { setErr((e as Error).message); setBusy(""); }
  };
  const parts = (a: DemoAccount) => {
    const m = /^(.*?)\s*\((.*)\)\s*$/.exec(a.label);
    return { name: m ? m[1] : a.label, hint: m ? m[2] : "" };
  };
  const featured = demo.accounts.find((a) => a.key === FEATURED);
  const others = demo.accounts.filter((a) => a.key !== FEATURED);
  return (
    <div>
      {err && <ErrorBox message={err} />}
      {!demo.demo_mode ? <p className="empty">Демо-режим выключен.</p> : (
        <>
          {featured && (
            <section className="demo-path" aria-label="Демонстрационный путь">
              <span className="demo-flag"><Icon name="eye" size={13} />Демонстрационный путь · подготовленные данные</span>
              <div className="demo-path-top">
                <Avatar name={parts(featured).name} />
                <div>
                  <h3>{parts(featured).name}</h3>
                  <p>Готовый подтверждённый кандидат: пройденная оценка, уровни по навыкам, рекомендации. Это отдельный демо-аккаунт — он не смешивается с данными новых пользователей.</p>
                </div>
                <button className="primary" disabled={!!busy} onClick={() => enter(featured)}>{busy === featured.key ? "Входим…" : "Открыть профиль"}</button>
              </div>
              <ol className="demo-steps">
                <li>Профиль подтверждённых компетенций: уровни и подтверждения</li>
                <li>Оценка и результат по компетенциям</li>
                <li>Рекомендованные вакансии</li>
                <li>Демо-компания: подбор → приглашение</li>
              </ol>
            </section>
          )}
          <h3 style={{ margin: "14px 0 4px", fontSize: 17 }}>Другие демо-сценарии</h3>
          <p className="muted" style={{ margin: "0 0 10px" }}>Готовые учётные записи — пароль не нужен.</p>
          <div className="demo-list">
            {others.map((a) => {
              const { name, hint } = parts(a);
              return (
                <div key={a.key} className="demo-item">
                  <div>
                    <b>{name}</b>
                    <span><Badge tone={a.role === "candidate" ? "info" : "brand"}>{a.role === "candidate" ? "Кандидат" : "Работодатель"}</Badge>
                      {hint && <Badge tone="muted">{hint}</Badge>}{a.fsp_id && <Badge tone="info">ФСП</Badge>}</span>
                    <p>{a.note}</p>
                  </div>
                  <button disabled={!!busy} onClick={() => enter(a)}>{busy === a.key ? "Входим…" : "Войти"}</button>
                </div>);
            })}
          </div>
          <p className="muted" style={{ margin: "12px 2px 0", fontSize: 13 }}>
            <b style={{ color: "var(--ink)" }}>Сценарий демонстрации.</b> Алексей Демо → оценка компетенций → профиль подтверждённых компетенций → подключение ФСП ID → Демо-компания → потребность → подбор → приглашение → принятие → открытие контактов.
          </p>
        </>
      )}
    </div>
  );
}
