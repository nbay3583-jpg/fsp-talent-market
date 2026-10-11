import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Session } from "./api";
import type { Catalog, Invitation } from "./types";
import {
  Badge, Card, CompanyMark, Empty, ErrorBox, FORMAT_RU, GRADE_RU, Icon, Kpi, LevelMeter, Loading, PageHead, Ring, SALARY_TYPE_RU, SalaryBanner, skillName, STATUS_RU, subLabel, VerificationBadge, money,
} from "./ui";
import { CandidateFit } from "./TeamFit";
import Shell, { type ShellCtx } from "./Shell";

interface Me {
  id: number; full_name: string; email: string; email_verified: boolean; phone: string | null; specialization: string | null;
  claimed_grade: string | null; verification_status: string; verified_grade: string | null;
  preferences: {
    salary_min: number | null; salary_type: string | null; work_formats: string[]; location: string | null;
    available_in_days: number | null; profile_visible: boolean; open_to_invitations: boolean;
    published?: boolean; publish_blockers?: string[];
  };
}
interface Breakdown {
  competency: string; percent: number | null; tasks: number | null; answered: number | null;
  points_earned: number | null; points_max: number | null; reliability: "none" | "limited" | "moderate" | "unknown";
}
interface Task { variant_id: number; competency: string; prompt: string; answer_type: "single" | "multi" | "number"; options: Record<string, string> | null }
type Answer = string | number | string[]
interface Attempt { attempt_id: number; target_grade: string; tasks: Task[]; remaining_seconds: number; saved_answers?: Record<string, Answer> }
interface Result {
  verification_status: string; claimed_grade: string; target_grade: string; achieved_sublevel: string | null;
  score: number; competency_scores: Record<string, number>;
  competency_breakdown?: Breakdown[];
}
interface Profile {
  specialization: string | null; claimed_grade: string | null; verification_status: string;
  verified_grade: string | null; verified_sublevel: string | null;
  assessment: { target_grade: string; verification_status: string; achieved_sublevel: string | null; score: number; competency_scores: Record<string, number>; competency_breakdown?: Breakdown[]; passed?: boolean; scored_at: string | null } | null;
  skills: {
    skill: string; name: string; claimed_level: string | null; claim_source: string; verified_level: string | null;
    verified_sublevel: string | null;
    confirmed: boolean;
    evidence: { type: string; confirmed: boolean; level: string | null; title: string | null }[];
  }[];
  fsp: { has_history: boolean; evidence_items: number };
}

const EVIDENCE_RU: Record<string, string> = {
  CORE_ASSESSMENT: "Основная оценка компетенций", TECHNOLOGY_ASSESSMENT: "Оценка по технологии",
  PROFESSIONAL_EXPERIENCE: "Самоописанный опыт (не проверен)", FSP_ACHIEVEMENT: "Достижение ФСП (демо-данные, не реальная проверка)", RECENT_CHALLENGE: "Свежее задание",
};
interface Job {
  id: number; company: string; position: string; start_date: string; end_date: string | null;
  stack: string[]; tasks: string; projects: string; achievements: string;
}
const SOURCE_RU: Record<string, string> = {
  self_reported: "заявлено кандидатом", core_assessment: "создано тестом", fsp: "демо-данные ФСП", experience: "самоописанный опыт",
};

type Tab = "overview" | "evidence" | "test" | "fit" | "invitations" | "profile";
const TITLES: Record<Tab, [string, string]> = {
  overview: ["Обзор", "Грейд, подтверждённые навыки и новые приглашения"],
  evidence: ["Профиль подтверждённых компетенций", "Заявка → подтверждение: что подтверждено оценкой, а что только заявлено"],
  test: ["Оценка навыков", "Основная оценка: подтверждение грейда J1–S3"],
  fit: ["Рекомендации", "Подходящие вакансии, интересы и анкета предпочтений"],
  invitations: ["Приглашения", "Предложения работодателей с зарплатной вилкой"],
  profile: ["Настройки профиля", "Личные данные, предпочтения и опыт"],
};
const LADDER = ["J1", "J2", "J3", "M1", "M2", "M3", "S1", "S2", "S3"];

export default function CandidateApp({ session, shell, demoMode }: { session: Session; shell: ShellCtx; demoMode?: boolean }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [name, setName] = useState("Кандидат");
  const [invs, setInvs] = useState<Invitation[] | null>(null);
  const [prof, setProf] = useState<Profile | null>(null);
  const reloadInvs = useCallback(() => {
    api<Invitation[]>("/api/candidates/me/invitations", { token: session.token }).then(setInvs).catch(() => setInvs([]));
  }, [session.token]);
  useEffect(() => {
    api<Me>("/api/candidates/me", { token: session.token }).then((m) => setName(m.full_name)).catch(() => undefined);
    reloadInvs();
  }, [session.token, reloadInvs]);
  useEffect(() => {  // sidebar grade card follows the real profile; refreshed when the tab changes (e.g. after a test)
    api<Profile>("/api/candidates/me/profile", { token: session.token }).then(setProf).catch(() => undefined);
  }, [session.token, tab]);
  const fresh = (invs ?? []).filter((i) => i.status === "SENT").length;
  const items = [
    { key: "overview", label: "Обзор", icon: "home" },
    { key: "evidence", label: "Мои компетенции", icon: "shield" },
    { key: "test", label: "Оценка навыков", icon: "check" },
    { key: "fit", label: "Рекомендации", icon: "star" },
    { key: "invitations", label: "Приглашения", icon: "mail", count: fresh },
    { key: "profile", label: "Настройки", icon: "gear" },
  ];
  const [title, sub] = TITLES[tab];
  const confirmed = prof ? prof.skills.filter((s) => s.verified_level).length : 0;
  const foot = prof && (
    <div className="side-card" aria-label="Мой грейд">
      Мой грейд
      <div className="grade-big">
        <strong>{prof.verified_sublevel ?? "—"}</strong>
        <span className="muted">{prof.verified_grade ? GRADE_RU[prof.verified_grade] : "не подтверждён"}</span>
      </div>
      <div className="progress thin" aria-hidden="true"><span style={{ width: `${prof.skills.length ? Math.round((confirmed / prof.skills.length) * 100) : 0}%` }} /></div>
      {confirmed} из {prof.skills.length} навыков подтверждено
    </div>
  );
  return (
    <Shell items={items} active={tab} onSelect={(k) => setTab(k as Tab)} who={{ label: name, role: "Кандидат" }} foot={foot} demoSession={session.demo}
      health={shell.health} demoMode={shell.demoMode} onLogout={shell.onLogout} onValidation={shell.onValidation}>
      {shell.banners}
      {session.demo && (
        <p className="demo-banner" role="note"><Icon name="eye" size={16} />Демонстрационный аккаунт: данные подготовлены заранее и отделены от реальных аккаунтов. Новый зарегистрированный кандидат начинает с пустого профиля.</p>
      )}
      <PageHead title={title} sub={sub} />
      {tab === "overview" && <OverviewTab session={session} invs={invs} go={setTab} />}
      {tab === "profile" && <ProfileTab session={session} />}
      {tab === "test" && <AssessmentTab session={session} demoMode={demoMode ?? shell.demoMode} goEvidence={() => setTab("evidence")} />}
      {tab === "evidence" && <EvidenceTab session={session} />}
      {tab === "fit" && <CandidateFit session={session} go={(t) => setTab(t as Tab)} />}
      {tab === "invitations" && <InvitationsTab session={session} onChange={reloadInvs} go={setTab} />}
    </Shell>
  );
}

const INV_TONE = (st: string): "bad" | "info" | "ok" => (st === "DECLINED" ? "bad" : st === "SENT" || st === "VIEWED" ? "info" : "ok");

function OverviewTab({ session, invs, go }: { session: Session; invs: Invitation[] | null; go: (t: Tab) => void }) {
  const [p, setP] = useState<Profile | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Profile>("/api/candidates/me/profile", { token: session.token }).then(setP).catch((e: Error) => setErr(e.message)); }, [session.token]);
  if (err) return <ErrorBox message={err} />;
  if (!p) return <Loading what="Загружаем обзор" />;
  const confirmed = p.skills.filter((s) => s.verified_level).length;
  const fresh = (invs ?? []).filter((i) => i.status === "SENT").length;
  const assessed = p.assessment !== null;
  const status = p.verification_status === "VERIFIED" ? "Подтверждён" : p.verification_status === "NOT_VERIFIED" ? "Не подтверждён" : "Оценка не пройдена";
  return (
    <div className="stack">
      {!assessed ? (
        <div className="next-step">
          <span className="kpi-icon"><Icon name="target" size={16} /></span>
          <div><b>Следующий шаг: подтвердите грейд</b><span className="muted">Без оценки работодатели видят грейд как заявленный, а навыки — как неподтверждённые.</span></div>
          <button className="primary" onClick={() => go("test")}>Пройти оценку <Icon name="arrow" size={16} /></button>
        </div>
      ) : fresh > 0 ? (
        <div className="next-step">
          <span className="kpi-icon"><Icon name="mail" size={16} /></span>
          <div><b>Новых приглашений: {fresh}</b><span className="muted">Откройте приглашение: зарплатная вилка указана, контакты откроются только по вашему согласию.</span></div>
          <button className="primary" onClick={() => go("invitations")}>Посмотреть</button>
        </div>
      ) : null}
      <div className="kpis">
        <Kpi tone="mint" icon="shield" label="Подтверждённый грейд" value={p.verified_sublevel ?? "—"} sub={p.verified_grade ? `${GRADE_RU[p.verified_grade]} · ${subLabel(p.verified_sublevel)}` : "пока не подтверждён"} />
        <Kpi icon="user" label="Заявленный грейд" value={p.claimed_grade ? GRADE_RU[p.claimed_grade] : "—"} sub={status} />
        <Kpi icon="check" label="Подтверждённые навыки" value={`${confirmed}`} progress={p.skills.length ? confirmed / p.skills.length : 0} sub={`из ${p.skills.length} в профиле`} />
        <Kpi icon="mail" label="Приглашения" value={`${invs?.length ?? "…"}`} sub={fresh > 0 ? `новых: ${fresh}` : "новых нет"} />
      </div>
      <div className="grid-main">
        <Card title="Навыки и технологии" aside={<button className="small" onClick={() => go("evidence")}>Профиль подтверждённых компетенций <Icon name="arrow" size={14} /></button>}>
          {p.skills.length === 0 ? <Empty compact icon="shield" title="Навыков пока нет">Пройдите оценку, чтобы они появились в профиле.</Empty> : (
            <div>
              {p.skills.map((s) => (
                <span key={s.skill} className={`chip-skill${s.verified_level ? " on" : ""}`} title={s.verified_level ? `подтверждено: ${GRADE_RU[s.verified_level]} ${subLabel(s.verified_sublevel)}` : "не подтверждено"}>
                  <Icon name={s.verified_level ? "tick" : "plus"} size={13} />{skillName(s.skill, s.name)}
                  {s.verified_level && <small>{s.verified_sublevel ?? GRADE_RU[s.verified_level]}</small>}
                </span>))}
            </div>)}
          {p.skills.length > 0 && <p className="muted" style={{ margin: "6px 0 0", fontSize: 13 }}>Мятные — подтверждены оценкой; серые — только заявлены.</p>}
        </Card>
        <Card title="Прогресс оценки" aside={<VerificationBadge status={p.verification_status} />}>
          {assessed ? (
            <div className="progress-card">
              <Ring value={p.assessment!.score} caption="верных" />
              <div>
                <b>{GRADE_RU[p.assessment!.target_grade]}</b>
                <p className="muted" style={{ margin: "2px 0 10px" }}>Последняя попытка · {Math.round(p.assessment!.score * 100)}% правильных ответов</p>
                <button onClick={() => go("test")}>Другой грейд / ещё раз</button>
              </div>
            </div>
          ) : (
            <div className="progress-card">
              <Ring value={0} caption="не начата" />
              <div><p className="muted" style={{ margin: "0 0 10px" }}>Оценка ещё не пройдена.</p><button className="primary" onClick={() => go("test")}>Пройти оценку</button></div>
            </div>
          )}
        </Card>
      </div>
      <Card title="Последние приглашения" aside={invs && invs.length > 0 ? <button className="small" onClick={() => go("invitations")}>Все приглашения</button> : undefined}>
        {!invs ? <Loading /> : invs.length === 0 ? (
          <Empty compact icon="mail" title="Приглашений пока нет">Работодатели находят вас по подтверждённым навыкам и пишут адресно — с зарплатной вилкой.</Empty>
        ) : invs.slice(0, 3).map((i) => (
          <div className="invite-row" key={i.id}>
            <CompanyMark name={i.company} />
            <div><b>{i.company}</b><div className="muted">{i.role} · {money(i.salary_from)}–{money(i.salary_to)} ₽ {i.salary_type}</div></div>
            <Badge tone={INV_TONE(i.status)}>{STATUS_RU[i.status] ?? i.status}</Badge>
          </div>))}
      </Card>
    </div>
  );
}

/** The server builds links from PUBLIC_BASE_URL (may not match the origin the app is served from); keep only the token. */
const localLink = (raw: string) => {
  const m = /verify_email=([^&\s]+)/.exec(raw);
  return m ? `${window.location.origin}/?verify_email=${m[1]}` : raw;
};

function EmailBanner({ session }: { session: Session }) {
  const [msg, setMsg] = useState("");
  const [link, setLink] = useState(() => { try { return sessionStorage.getItem("fsp.demo_verify") ?? ""; } catch { return ""; } });
  const resend = async () => {
    try {
      const r = await api<{ sent: boolean; demo_verification_link?: string }>("/api/candidates/me/email/resend", { method: "POST", token: session.token });
      if (r.sent) setMsg("Письмо отправлено. Перейдите по ссылке из письма.");
      else if (r.demo_verification_link) { setMsg("Демо-режим: почтовый сервер не настроен, письмо не отправлено."); setLink(r.demo_verification_link); }
      else setMsg("Почтовый сервер не настроен, письмо не отправлено. Обратитесь к администратору.");
    } catch (e) {
      const m = /retry in (\d+)s/.exec((e as Error).message);
      setMsg(m ? `Повторная отправка возможна через ${m[1]} с.` : (e as Error).message);
    }
  };
  return (
    <div className="warn">
      <p>Email не подтверждён: до подтверждения профиль нельзя опубликовать для подбора.</p>
      <button onClick={resend}>Отправить письмо ещё раз</button>
      {msg && <p role="status">{msg}</p>}
      {link && <p><span className="muted">Демо-режим, почта не отправляется. </span><a href={localLink(link)}>Подтвердить email</a></p>}
    </div>
  );
}

const EMPTY_JOB = { company: "", position: "", start_date: "", end_date: "", stack: [] as string[], tasks: "", projects: "", achievements: "" };

function ExperienceCard({ session, skills }: { session: Session; skills: { code: string; name: string }[] }) {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [f, setF] = useState(EMPTY_JOB);
  const [editing, setEditing] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    api<{ items: Job[] }>("/api/candidates/me/experience", { token: session.token }).then((r) => setJobs(r.items)).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  useEffect(load, [load]);
  const save = async () => {
    setErr("");
    const body = { ...f, end_date: f.end_date || null };
    try {
      if (editing === null) await api("/api/candidates/me/experience", { token: session.token, body });
      else await api(`/api/candidates/me/experience/${editing}`, { method: "PATCH", token: session.token, body });
      setF(EMPTY_JOB); setEditing(null); load();
    } catch (e) { setErr((e as Error).message); }
  };
  const remove = async (id: number) => {
    try { await api(`/api/candidates/me/experience/${id}`, { method: "DELETE", token: session.token }); load(); }
    catch (e) { setErr((e as Error).message); }
  };
  const edit = (j: Job) => { setEditing(j.id); setF({ ...j, end_date: j.end_date ?? "" }); };
  const toggle = (code: string) => setF({ ...f, stack: f.stack.includes(code) ? f.stack.filter((x) => x !== code) : [...f.stack, code] });
  return (
    <Card title="Опыт работы" aside={<Badge tone="muted">не подтверждено платформой</Badge>}>
      <p className="muted">Опыт из резюме — это контекст для подбора. Он не подтверждает навыки и не меняет грейд: подтверждение даёт только оценка и достижения ФСП.</p>
      {jobs && jobs.length === 0 && <Empty>Опыт пока не добавлен.</Empty>}
      {jobs?.map((j) => (
        <div key={j.id} className="job">
          <b>{j.position}</b>, {j.company} · {j.start_date} — {j.end_date ?? "по настоящее время"}
          {j.stack.length > 0 && <div>{j.stack.map((s) => <Badge key={s} tone="muted">{skillName(s)}</Badge>)}</div>}
          {j.tasks && <p>Задачи: {j.tasks}</p>}
          {j.projects && <p>Проекты: {j.projects}</p>}
          {j.achievements && <p>Достижения: {j.achievements}</p>}
          <div className="row"><button onClick={() => edit(j)}>Изменить</button><button onClick={() => remove(j.id)}>Удалить</button></div>
        </div>
      ))}
      <h4>{editing === null ? "Добавить место работы" : "Изменить место работы"}</h4>
      <div className="row">
        <label>Компания<input value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} /></label>
        <label>Должность<input value={f.position} onChange={(e) => setF({ ...f, position: e.target.value })} /></label>
      </div>
      <div className="row">
        <label>Начало<input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></label>
        <label>Окончание (пусто — работаю сейчас)<input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></label>
      </div>
      <div className="form-sec">Стек</div>
      <div className="chip-pick">
        {skills.map((s) => <label key={s.code} className={f.stack.includes(s.code) ? "on" : ""}><input type="checkbox" checked={f.stack.includes(s.code)} onChange={() => toggle(s.code)} /><span className="mark" />{skillName(s.code, s.name)}</label>)}
      </div>
      <label>Задачи<textarea value={f.tasks} onChange={(e) => setF({ ...f, tasks: e.target.value })} /></label>
      <label>Проекты<textarea value={f.projects} onChange={(e) => setF({ ...f, projects: e.target.value })} /></label>
      <label>Достижения<textarea value={f.achievements} onChange={(e) => setF({ ...f, achievements: e.target.value })} /></label>
      {err && <ErrorBox message={err} />}
      <div className="row">
        <button className="primary" disabled={!f.company || !f.position || !f.start_date} onClick={save}>{editing === null ? "Добавить" : "Сохранить"}</button>
        {editing !== null && <button onClick={() => { setEditing(null); setF(EMPTY_JOB); }}>Отмена</button>}
      </div>
    </Card>
  );
}

function ProfileTab({ session }: { session: Session }) {
  const [me, setMe] = useState<Me | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ full_name: "", specialization: "backend_python", claimed_grade: "MIDDLE", phone: "",
    salary_min: "", salary_type: "GROSS", location: "", available_in_days: "", formats: [] as string[], visible: true, open: true });
  useEffect(() => {
    Promise.all([api<Me>("/api/candidates/me", { token: session.token }), api<Catalog>("/api/catalog")])
      .then(([m, c]) => {
        setMe(m); setCatalog(c);
        const p = m.preferences;
        setForm({ full_name: m.full_name, specialization: m.specialization ?? "backend_python", claimed_grade: m.claimed_grade ?? "MIDDLE",
          phone: m.phone ?? "", salary_min: p.salary_min?.toString() ?? "", salary_type: p.salary_type ?? "GROSS",
          location: p.location ?? "", available_in_days: p.available_in_days?.toString() ?? "", formats: p.work_formats,
          visible: p.profile_visible, open: p.open_to_invitations });
      })
      .catch((e: Error) => setErr(e.message));
  }, [session.token]);
  if (err) return <ErrorBox message={err} />;
  if (!me || !catalog) return <Loading what="Загружаем профиль" />;
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => { setSaved(false); setForm({ ...form, [k]: v }); };
  const toggleFormat = (f: string) => set("formats", form.formats.includes(f) ? form.formats.filter((x) => x !== f) : [...form.formats, f]);
  const save = async () => {
    setErr("");
    try {
      await api("/api/candidates/me/profile", { method: "PATCH", token: session.token, body: {
        full_name: form.full_name, specialization: form.specialization, claimed_grade: form.claimed_grade } });
      await api("/api/candidates/me/preferences", { method: "PATCH", token: session.token, body: {
        phone: form.phone || null, salary_min: form.salary_min ? Number(form.salary_min) : null,
        salary_type: form.salary_min ? form.salary_type : null, work_formats: form.formats.length ? form.formats : null,
        location: form.location || null, available_in_days: form.available_in_days ? Number(form.available_in_days) : null,
        profile_visible: form.visible,
        open_to_invitations: form.open } });
      setSaved(true);
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="grid-2" style={{ alignItems: "start" }}>
      <Card title="Предпочтения для подбора">
        <div className="row">
          <label>Минимальная зарплата, ₽<input inputMode="numeric" value={form.salary_min} onChange={(e) => set("salary_min", e.target.value.replace(/\D/g, ""))} /></label>
          <label>Тип<select value={form.salary_type} onChange={(e) => set("salary_type", e.target.value)}><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
        </div>
        <div className="form-sec">Формат работы</div>
        <div className="chip-pick">
          {Object.entries(FORMAT_RU).map(([k, v]) => (
            <label key={k} className={form.formats.includes(k) ? "on" : ""}><input type="checkbox" checked={form.formats.includes(k)} onChange={() => toggleFormat(k)} /><span className="mark" />{v}</label>
          ))}
        </div>
        <div className="row">
          <label>Город<input value={form.location} onChange={(e) => set("location", e.target.value)} /></label>
          <label>Готов выйти через, дней<input inputMode="numeric" value={form.available_in_days} onChange={(e) => set("available_in_days", e.target.value.replace(/\D/g, ""))} /></label>
        </div>
        <label className="toggle-row"><span>Профиль виден работодателям<small>без контактов</small></span><input type="checkbox" checked={form.visible} onChange={(e) => set("visible", e.target.checked)} /></label>
        <label className="toggle-row"><span>Готов получать приглашения<small>адресные предложения с зарплатной вилкой</small></span><input type="checkbox" checked={form.open} onChange={(e) => set("open", e.target.checked)} /></label>
        {form.visible && !me.email_verified && <p className="muted">Профиль станет виден работодателям после подтверждения email — пока он скрыт.</p>}
        {me.preferences?.publish_blockers?.includes("not_open_to_invitations") && <p className="muted">Включите «Готов получать приглашения», иначе вы не попадёте в подбор.</p>}
        <button className="primary" style={{ marginTop: 10 }} onClick={save}>Сохранить</button>
        {saved && <p className="ok" role="status">Сохранено</p>}
        {err && <ErrorBox message={err} />}
      </Card>
      <Card title="Кандидат" aside={<VerificationBadge status={me.verification_status} />}>
        <p className="muted">Заявленный грейд — это заявка. Подтверждённый грейд платформы определяет только основная оценка компетенций: не резюме, не достижения ФСП и не вакансия.</p>
        <label>Имя<input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></label>
        <label>Email (виден только вам)<input value={me.email} disabled /></label>
        {me.email_verified ? <p className="ok">Email подтверждён.</p> : <EmailBanner session={session} />}
        <label>Телефон (скрыт до вашего согласия)<input type="tel" inputMode="tel" placeholder="+7 900 123-45-67" maxLength={24} value={form.phone} onChange={(e) => set("phone", e.target.value.replace(/[^\d\s+().-]/g, ""))} /></label>
        <div className="row">
          <label>Специализация
            <select value={form.specialization} onChange={(e) => set("specialization", e.target.value)}>
              {catalog.specializations.map((s) => <option key={s.code} value={s.code}>{s.name}{s.assessment_available ? "" : " — оценка пока недоступна"}</option>)}
            </select>
          </label>
          <label>Желаемый грейд
            <select value={form.claimed_grade} onChange={(e) => set("claimed_grade", e.target.value)}>
              {Object.keys(catalog.grades).map((g) => <option key={g} value={g}>{GRADE_RU[g]}</option>)}
            </select>
          </label>
        </div>
        {catalog.specializations.find((x) => x.code === form.specialization)?.assessment_available === false
          ? <p className="warn">Для этой специализации тестирование ещё не реализовано: профиль сохранится, но подтвердить грейд можно только по Backend / Python.</p>
          : <p className="muted">Полная оценка реализована для Backend / Python.</p>}
      </Card>
      <div style={{ gridColumn: "1 / -1" }}><ExperienceCard session={session} skills={catalog.skills} /></div>
    </div>
  );
}

const COMP_ORDER = ["python", "sql", "api_fastapi", "testing", "docker_basics", "system_thinking"];
const PASS_PCT: Record<string, number> = { JUNIOR: 60, MIDDLE: 70, SENIOR: 75 };

// 0 is a valid numeric answer: only missing/blank strings/empty lists count as unanswered
export const answeredOf = (a: Answer | undefined | null) => (Array.isArray(a) ? a.length > 0 : typeof a === "number" ? Number.isFinite(a) : typeof a === "string" && a.trim() !== "");

function AssessmentTab({ session, demoMode, goEvidence }: { session: Session; demoMode: boolean; goEvidence: () => void }) {
  const [grade, setGrade] = useState("MIDDLE");
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<Record<number, Answer>>({});
  const [left, setLeft] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const start = async () => {
    setErr(""); setResult(null); setBusy(true);
    try {
      const a = await api<Attempt>("/api/assessments", { token: session.token, body: { target_grade: grade } });
      setAttempt(a); setLeft(a.remaining_seconds);
      setAnswers(Object.fromEntries(Object.entries(a.saved_answers ?? {}).map(([k, v]) => [Number(k), typeof v === "number" ? String(v) : v])));
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 409
        ? (e.message.includes("not available yet") ? "Тестирование для выбранной специализации ещё не реализовано. Доступна оценка Backend / Python." : `Повторная попытка пока недоступна: ${e.message}`)
        : (e as Error).message);
    } finally { setBusy(false); }
  };
  const fillReference = async () => {
    if (!attempt) return;
    const r = await api<{ answers: Record<string, Answer> }>(`/api/demo/assessments/${attempt.attempt_id}/reference-answers`, { token: session.token });
    setAnswers(Object.fromEntries(Object.entries(r.answers).map(([k, v]) => [Number(k), typeof v === "number" ? String(v) : v])));
  };
  const submit = async () => {
    if (!attempt) return;
    setBusy(true); setErr("");
    try {
      const r = await api<Result>(`/api/assessments/${attempt.attempt_id}/submit`, { token: session.token, body: { answers } });
      setResult(r); setAttempt(null);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  useEffect(() => {  // countdown is driven by the server deadline; the client only renders it
    if (!attempt) return;
    const t = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [attempt]);
  const setAnswer = (id: number, v: Answer) => {
    setAnswers((prev) => ({ ...prev, [id]: v }));
    if (attempt) api(`/api/assessments/${attempt.attempt_id}/answers`, { method: "PUT", token: session.token, body: { answers: { [id]: v } } }).catch(() => undefined);
  };
  if (result) return <ResultCard result={result} goEvidence={goEvidence} again={() => setResult(null)} />;
  if (!attempt) {
    return (
      <div className="assess-start">
        <section className="assess-hero" aria-label="Основная оценка">
          <span className="hero-eyebrow" style={{ alignSelf: "flex-start" }}><Icon name="shield" size={14} />Основная оценка · Backend / Python</span>
          <h2>Подтвердите грейд за 15–23 минуты</h2>
          <p>11 заданий по шести компетенциям. Варианты заданий параметризованы: у каждого кандидата свои числа и сценарии с тем же уровнем сложности и теми же критериями. Оценка полностью детерминирована — без нейросетей.</p>
          <div className="facts">
            <div className="fact"><b>11</b><span>заданий</span></div>
            <div className="fact"><b>15–23</b><span>минуты на выполнение</span></div>
            <div className="fact"><b>6</b><span>компетенций</span></div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: 13, marginBottom: 6 }}>Что проверяется</div>
            <div className="comp-list">{COMP_ORDER.map((c) => <span key={c} className="chip-skill on" style={{ margin: 0 }}><Icon name="tick" size={13} />{skillName(c)}</span>)}</div>
          </div>
        </section>
        <Card title="Выберите грейд для подтверждения">
          <div className="grade-cards" role="radiogroup" aria-label="Грейд, который вы подтверждаете">
            {Object.entries(GRADE_RU).map(([k, v]) => (
              <button key={k} role="radio" aria-checked={grade === k} className={`grade-card${grade === k ? " active" : ""}`} onClick={() => setGrade(k)}>
                <b>{v}</b><span>порог {PASS_PCT[k]}%</span>
              </button>))}
          </div>
          <button className="primary large" style={{ width: "100%" }} disabled={busy} onClick={start}><Icon name="bolt" size={16} />Начать оценку</button>
          {err && <div style={{ marginTop: 12 }}><ErrorBox message={err} /></div>}
          <ul className="muted" style={{ margin: "14px 0 0", paddingLeft: 18, fontSize: 13 }}>
            <li>Ответы сохраняются автоматически; по истечении времени отправятся сохранённые.</li>
            <li>Верхний подуровень (J2/M2/S2 и выше) — от 85% правильных ответов.</li>
            <li>Повторная попытка того же грейда после неуспеха — через 7 дней.</li>
          </ul>
        </Card>
      </div>
    );
  }
  const total = attempt.tasks.length;
  const answered = attempt.tasks.filter((t) => answeredOf(answers[t.variant_id])).length;
  const done = answered === total;
  const mm = String(Math.floor(left / 60)).padStart(2, "0"), ss = String(left % 60).padStart(2, "0");
  const jump = (id: number) => document.getElementById(`task-${id}`)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  return (
    <div>
      <div className="test-bar">
        <div className="test-bar-inner">
          <div>
            <h3>Оценка {GRADE_RU[attempt.target_grade]} · {total} заданий</h3>
            <span className="muted">Отвечено: {answered} из {total}</span>
          </div>
          <span className={`timer${left <= 60 ? " low" : ""}`} role="timer"><Icon name="clock" size={18} />Осталось {mm}:{ss}</span>
          <div className="progress" aria-hidden="true"><span style={{ width: `${Math.round((answered / Math.max(1, total)) * 100)}%` }} /></div>
          <div className="navigator" aria-label="Навигация по заданиям">
            {attempt.tasks.map((t, i) => (
              <button key={t.variant_id} className={answeredOf(answers[t.variant_id]) ? "done" : ""} aria-label={`Задание ${i + 1}${answeredOf(answers[t.variant_id]) ? ", есть ответ" : ""}`} onClick={() => jump(t.variant_id)}>{i + 1}</button>
            ))}
            {demoMode && <button style={{ width: "auto", padding: "0 12px" }} onClick={fillReference}>Демо: эталонные ответы</button>}
          </div>
        </div>
      </div>
      {attempt.tasks.map((t, i) => (
        <section key={t.variant_id} id={`task-${t.variant_id}`} className={`card task-card${answeredOf(answers[t.variant_id]) ? " done" : ""}`} style={{ scrollMarginTop: 150 }}>
          <div className="task-head"><span className="task-no">{i + 1}</span><h3>{skillName(t.competency)}</h3>
            <span className="muted" style={{ marginLeft: "auto", fontSize: 13 }}>{t.answer_type === "multi" ? "несколько ответов" : t.answer_type === "number" ? "число" : "один ответ"}</span></div>
          <pre className="prompt">{t.prompt}</pre>
          {t.answer_type === "number" ? (
            <input inputMode="decimal" aria-label="Ответ" value={(answers[t.variant_id] as string) ?? ""} onChange={(e) => setAnswer(t.variant_id, e.target.value.replace(/[^0-9.,-]/g, ""))} />
          ) : Object.entries(t.options ?? {}).map(([k, v]) => (
            <label key={k} className="option">
              {t.answer_type === "multi" ? (
                <input type="checkbox" checked={((answers[t.variant_id] as string[]) ?? []).includes(k)}
                  onChange={() => { const cur = (answers[t.variant_id] as string[]) ?? []; setAnswer(t.variant_id, cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]); }} />
              ) : (
                <input type="radio" name={`q${t.variant_id}`} checked={answers[t.variant_id] === k} onChange={() => setAnswer(t.variant_id, k)} />
              )}
              <b>{k}</b> <span>{v}</span>
            </label>
          ))}
        </section>
      ))}
      <div className="sticky-submit">
        <button className="primary large" disabled={!done || busy} onClick={submit}>Отправить ответы</button>
        {!done && <p className="muted" style={{ margin: "8px 0 0" }}>Ответьте на все задания, чтобы отправить ответы. Ответы сохраняются автоматически; по истечении времени отправятся сохранённые.</p>}
        {err && <ErrorBox message={err} />}
      </div>
    </div>
  );
}

function tasksWord(n: number): string {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return "задание";
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "задания";
  return "заданий";
}

const RELIABILITY_RU: Record<string, string> = {
  none: "в этой попытке заданий по направлению не было — оценки нет",
  limited: "проверено малым числом заданий — это ориентир, а не подтверждение уровня по технологии",
  moderate: "направление проверено несколькими заданиями; результат всё равно относится только к этой попытке",
  unknown: "число заданий для этой попытки не сохранено — показан только процент",
};

function CompBars({ scores, breakdown }: { scores: Record<string, number>; breakdown?: Breakdown[] }) {
  const rows: Breakdown[] = breakdown && breakdown.length
    ? breakdown
    : [...COMP_ORDER.filter((k) => k in scores), ...Object.keys(scores).filter((k) => !COMP_ORDER.includes(k))]
        .map((k) => ({ competency: k, percent: scores[k], tasks: null, answered: null, points_earned: null, points_max: null, reliability: "unknown" as const }));
  return (
    <div className="comp-bars">
      {rows.map((r) => {
        const pct = r.percent === null ? null : Math.round(r.percent * 100);
        const detail = r.tasks === null ? null
          : r.tasks === 0 ? "заданий не было"
          : `${r.tasks} ${tasksWord(r.tasks)}${r.points_max !== null ? ` · ${r.points_earned} из ${r.points_max} баллов` : ""}${r.answered !== null && r.answered < r.tasks ? ` · без ответа: ${r.tasks - r.answered}` : ""}`;
        return (
          <div className={`comp-bar${r.reliability === "none" ? " empty" : ""}`} key={r.competency}>
            <span>{skillName(r.competency)}</span>
            <div className="progress" aria-hidden="true"><span style={{ width: `${pct ?? 0}%` }} /></div>
            <b>{pct === null ? "—" : `${pct}%`}</b>
            {detail && <small className="comp-detail">{detail}</small>}
            {(r.reliability === "limited" || r.reliability === "none") && <small className="comp-note">{RELIABILITY_RU[r.reliability]}</small>}
          </div>);
      })}
    </div>
  );
}

function CompCaveat() {
  return (
    <p className="muted comp-caveat">
      Это доля верных ответов в одной попытке комплексной оценки, а не независимый сертификат по технологии.
      Направления проверены небольшим числом заданий (обычно 1–3), поэтому процент — ориентир.
    </p>
  );
}

function ResultCard({ result, goEvidence, again }: { result: Result; goEvidence: () => void; again: () => void }) {
  const ok = result.verification_status === "VERIFIED";
  return (
    <Card title="Результат основной оценки компетенций" aside={<VerificationBadge status={result.verification_status} />}>
      <div className="result-hero">
        <Ring size={110} value={result.score} caption="верных" />
        <div>
          <p className="big" style={{ marginTop: 0 }}>Backend / {GRADE_RU[result.target_grade]}{ok && result.achieved_sublevel ? ` (${result.achieved_sublevel})` : ""}</p>
          {ok ? (
            <p className="ok">Уровень подтверждён тестом. Он появился в вашем профиле подтверждённых компетенций.</p>
          ) : (
            <p style={{ margin: 0 }}>
              Грейд <b>{GRADE_RU[result.claimed_grade]}</b> пока не подтверждён. Заявленный грейд {GRADE_RU[result.claimed_grade]} сохраняется (не подтверждён) — платформа не понижает вас автоматически до Junior.
              Можно пройти повторную попытку после паузы или оценку другого грейда.
            </p>
          )}
        </div>
      </div>
      <h4>Результат по направлениям</h4>
      <CompBars scores={result.competency_scores} breakdown={result.competency_breakdown} />
      <CompCaveat />
      <div className="row" style={{ marginTop: 16 }}><button className="primary" onClick={goEvidence}>Открыть профиль подтверждённых компетенций</button><button onClick={again}>Закрыть</button></div>
    </Card>
  );
}

function EvidenceIcon({ e }: { e: Profile["skills"][number]["evidence"][number] }) {
  if (e.type === "FSP_ACHIEVEMENT") return <span className="ico info"><Icon name="trophy" size={13} /></span>;
  if (e.type === "PROFESSIONAL_EXPERIENCE") return <span className="ico no"><Icon name="doc" size={13} /></span>;
  if (e.type === "RECENT_CHALLENGE") return <span className="ico"><Icon name="bolt" size={13} /></span>;
  return <span className={`ico${e.confirmed ? "" : " no"}`}><Icon name={e.confirmed ? "tick" : "warn"} size={13} /></span>;
}
function evidenceTitle(e: Profile["skills"][number]["evidence"][number]): string {
  if (e.type === "FSP_ACHIEVEMENT") return "Демо-данные ФСП";
  if (e.type === "CORE_ASSESSMENT" || e.type === "TECHNOLOGY_ASSESSMENT") return e.confirmed ? "Подтверждено тестом" : "Не подтверждено тестом";
  return e.confirmed ? "Подтверждено" : "Не подтверждено";
}

function EvidenceTab({ session }: { session: Session }) {
  const [p, setP] = useState<Profile | null>(null);
  const [err, setErr] = useState("");
  const [fsp, setFsp] = useState(session.fspId ?? "");
  const [fspMsg, setFspMsg] = useState("");
  const load = useCallback(() => {
    api<Profile>("/api/candidates/me/profile", { token: session.token }).then(setP).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  useEffect(load, [load]);
  const link = async () => {
    setFspMsg("");
    try {
      const r = await api<{ evidence_added: number; has_history: boolean }>("/api/candidates/me/fsp", { token: session.token, body: { fsp_id: fsp } });
      setFspMsg(r.has_history ? `Добавлено подтверждений: ${r.evidence_added}` : "ФСП ID подтверждён, достижений пока нет — это не влияет на ваш уровень.");
      load();
    } catch (e) { setFspMsg((e as Error).message); }
  };
  if (err) return <ErrorBox message={err} />;
  if (!p) return <Loading what="Собираем профиль подтверждённых компетенций" />;
  const confirmed = p.skills.filter((s) => s.verified_level).length;
  const claimedOnly = p.skills.length - confirmed;
  const evidenceCount = p.skills.reduce((n, s) => n + s.evidence.length, 0);
  const vIdx = p.verified_sublevel ? LADDER.indexOf(p.verified_sublevel) : -1;
  return (
    <div className="stack">
      <Card title="Профиль подтверждённых компетенций" aside={<VerificationBadge status={p.verification_status} />}>
        <div className="summary-split">
          <Ring size={104} value={p.skills.length ? confirmed / p.skills.length : 0} label={`${confirmed}/${p.skills.length}`} caption="навыков" />
          <div>
            <p className="big" style={{ margin: 0 }}>Backend / {p.claimed_grade ? GRADE_RU[p.claimed_grade] : "—"} <span className="muted" style={{ fontWeight: 500, fontSize: 15 }}>(заявлено кандидатом, не проверено)</span></p>
            <div style={{ marginTop: 6 }}>
              {p.verified_grade
                ? <Badge tone="ok">подтверждено: {GRADE_RU[p.verified_grade]} {subLabel(p.verified_sublevel)}</Badge>
                : <Badge tone="muted">грейд не подтверждён</Badge>}
            </div>
            {p.verification_status === "NOT_VERIFIED" && <p style={{ margin: "6px 0 0" }}>Заявленный грейд не подтверждён. Он сохранён — платформа не заменяет его более низким.</p>}
            {p.verification_status === "UNVERIFIED" && <p className="muted" style={{ margin: "6px 0 0" }}>Пройдите основную оценку компетенций, чтобы подтвердить грейд.</p>}
            <div className="stat-row">
              <span className="stat-pill ok"><b>{confirmed}</b>подтверждено</span>
              <span className="stat-pill"><b>{claimedOnly}</b>только заявлено</span>
              <span className="stat-pill"><b>{evidenceCount}</b>подтверждений</span>
            </div>
          </div>
        </div>
        <div className="ladder" role="img" aria-label={`Шкала грейдов J1–S3${p.verified_sublevel ? `, подтверждён ${p.verified_sublevel}` : ""}`}>
          {LADDER.map((l, i) => (
            <div key={l} className={`rung${i <= vIdx ? " reached" : ""}${i === vIdx ? " current" : ""}`}><i /><span>{l}</span></div>
          ))}
        </div>
        <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>Здесь нет единого «рейтинга кандидата»: только заявки и то, чем они подтверждены.</p>
      </Card>

      {p.assessment && (
        <Card title="Результат основной оценки" aside={<VerificationBadge status={p.assessment.verification_status} />}>
          <p style={{ margin: 0 }}>Попытка на {GRADE_RU[p.assessment.target_grade]} · {Math.round(p.assessment.score * 100)}% верных ответов в целом (порог {PASS_PCT[p.assessment.target_grade] ?? "—"}%)</p>
          <h4>Результат по направлениям</h4>
          <CompBars scores={p.assessment.competency_scores} breakdown={p.assessment.competency_breakdown} />
          <CompCaveat />
        </Card>
      )}

      {p.skills.length === 0 ? (
        <Empty icon="shield" title="Подтверждённых навыков пока нет">Заявки без подтверждения ничего не меняют. Пройдите оценку — навыки появятся здесь с уровнем и источником.</Empty>
      ) : (
        <div>
          <h3 style={{ margin: "0 0 10px", fontSize: 15.5 }}>Навыки: заявка → подтверждение</h3>
          <div className="skill-cards">
            {p.skills.map((s) => (
              <article key={s.skill} className={`skill-card${s.verified_level ? " on" : ""}`}>
                <div className="skill-card-head">
                  <div><b>{skillName(s.skill, s.name)}</b>
                    <small>{s.claimed_level ? `заявлено: ${GRADE_RU[s.claimed_level]}` : "заявка не указывалась"} · {SOURCE_RU[s.claim_source] ?? s.claim_source}</small></div>
                  {s.verified_level ? <span className="lvl-tag">{GRADE_RU[s.verified_level]} {subLabel(s.verified_sublevel)}</span> : <span className="lvl-tag none">не подтверждён</span>}
                </div>
                <LevelMeter claimed={s.claimed_level} verified={s.verified_level} sublevel={s.verified_sublevel} />
                <div className="evid">
                  {s.evidence.length === 0 ? <span className="muted">нет подтверждений</span> : s.evidence.slice(0, 2).map((e, i) => (
                    <div key={i} className="evid-item">
                      <EvidenceIcon e={e} />
                      <div><b>{evidenceTitle(e)}</b><small>{EVIDENCE_RU[e.type] ?? e.type}{e.title ? ` · ${e.title}` : ""}</small></div>
                    </div>))}
                  {s.evidence.length > 2 && (
                    <details><summary>История подтверждений ({s.evidence.length - 2})</summary>
                      {s.evidence.slice(2).map((e, i) => (
                        <div key={i} className="evid-item">
                          <EvidenceIcon e={e} />
                          <div><b>{evidenceTitle(e)}</b><small>{EVIDENCE_RU[e.type] ?? e.type}{e.title ? ` · ${e.title}` : ""}</small></div>
                        </div>))}
                    </details>)}
                </div>
              </article>))}
          </div>
          <p className="muted" style={{ margin: "8px 0 0", fontSize: 13 }}>Шкала: заполненная часть — подтверждённый платформой уровень; жёлтая рамка — заявленный.</p>
        </div>
      )}

      <Card title="Достижения ФСП (демо-данные)">
        {p.fsp.has_history ? <p className="ok">Найдено подтверждений: {p.fsp.evidence_items}. Они привязаны к релевантным навыкам и не меняют ваш уровень.</p>
          : <Empty>Истории ФСП нет — это нормально. Отсутствие достижений не ухудшает ваш уровень и профиль.</Empty>}
        <div className="fsp-link" style={{ marginTop: 10 }}>
          <input placeholder="ФСП ID, например FSP-1001" aria-label="ФСП ID" value={fsp} onChange={(e) => setFsp(e.target.value)} />
          <button onClick={link} disabled={!fsp}>Подключить ФСП ID (демо)</button>
        </div>
        {fspMsg && <p role="status">{fspMsg}</p>}
      </Card>
    </div>
  );
}

function InviteHelp({ session, go }: { session: Session; go: (t: Tab) => void }) {
  const [state, setState] = useState<{ assessed: boolean; visible: boolean; open: boolean } | null>(null);
  useEffect(() => {
    Promise.all([api<Profile>("/api/candidates/me/profile", { token: session.token }), api<Me>("/api/candidates/me", { token: session.token })])
      .then(([p, m]) => setState({ assessed: p.assessment !== null, visible: m.preferences.profile_visible && m.email_verified, open: m.preferences.open_to_invitations }))
      .catch(() => undefined);
  }, [session.token]);
  const steps: { done: boolean; text: string; to: Tab; cta: string }[] = state ? [
    { done: state.assessed, text: "Пройти оценку компетенций", to: "test", cta: "Пройти" },
    { done: state.visible, text: "Профиль виден работодателям (нужен подтверждённый email)", to: "profile", cta: "Настройки" },
    { done: state.open, text: "Готов получать приглашения", to: "profile", cta: "Настройки" },
  ] : [];
  return (
    <Empty icon="mail" title="Приглашений пока нет"
      action={steps.length > 0 ? (
        <ul className="help-steps">
          {steps.map((st) => (
            <li key={st.text} className={st.done ? "done" : ""}>
              <span className="ico">{st.done && <Icon name="tick" size={13} />}</span>{st.text}
              {!st.done && <button className="small" onClick={() => go(st.to)}>{st.cta}</button>}
            </li>))}
        </ul>) : undefined}>
      Работодатели находят вас по подтверждённым навыкам и пишут адресно — с зарплатной вилкой. Контакты открываются только после вашего согласия.
    </Empty>
  );
}

const FLOW: [string, string][] = [["SENT", "Отправлено"], ["VIEWED", "Просмотрено"], ["ACCEPTED", "Принято"], ["CONTACTS_UNLOCKED", "Контакты открыты"]];

function InvitationsTab({ session, onChange, go }: { session: Session; onChange: () => void; go: (t: Tab) => void }) {
  const [list, setList] = useState<Invitation[] | null>(null);
  const [open, setOpen] = useState<Invitation | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    api<Invitation[]>("/api/candidates/me/invitations", { token: session.token }).then((l) => { setList(l); onChange(); }).catch((e: Error) => setErr(e.message));
  }, [session.token, onChange]);
  useEffect(load, [load]);
  const view = async (id: number) => { setOpen(await api<Invitation>(`/api/candidates/me/invitations/${id}`, { token: session.token })); load(); };
  const respond = async (id: number, action: "accept" | "decline") => {
    try { setOpen(await api<Invitation>(`/api/candidates/me/invitations/${id}/${action}`, { token: session.token, method: "POST" })); load(); }
    catch (e) { setErr((e as Error).message); }
  };
  if (err) return <ErrorBox message={err} />;
  if (!list) return <Loading what="Загружаем приглашения" />;
  if (list.length === 0) return <InviteHelp session={session} go={go} />;
  const reached = open ? FLOW.findIndex(([k]) => k === open.status) : -1;
  return (
    <div className="inv-layout">
      <div>
        {list.map((i) => (
          <button key={i.id} className={`inv-item${open?.id === i.id ? " active" : ""}${i.status === "SENT" ? " fresh" : ""}`} onClick={() => view(i.id)}>
            <CompanyMark name={i.company} />
            <span><b>{i.company}</b><span className="muted" style={{ fontWeight: 400 }}>{i.role}</span></span>
            <span className="meta"><span>{money(i.salary_from)}–{money(i.salary_to)} ₽ {i.salary_type}</span><Badge tone={INV_TONE(i.status)}>{STATUS_RU[i.status]}</Badge></span>
          </button>))}
      </div>
      {open ? (
        <Card title={`${open.company} — ${open.role}`} aside={<Badge tone={INV_TONE(open.status)}>{STATUS_RU[open.status]}</Badge>}>
          <div className="timeline" aria-label="Статус приглашения">
            {open.status === "DECLINED"
              ? <><span className="on">Отправлено</span><span className="bad">Отклонено</span></>
              : FLOW.map(([k, l], i) => <span key={k} className={i <= reached ? "on" : ""}>{l}</span>)}
          </div>
          <SalaryBanner from={open.salary_from} to={open.salary_to} type={open.salary_type} />
          <p><b>Формат:</b> {FORMAT_RU[open.work_format] ?? open.work_format}</p>
          <p style={{ whiteSpace: "pre-wrap" }}>{open.description}</p>
          <blockquote>{open.message}</blockquote>
          {(open.status === "SENT" || open.status === "VIEWED") ? (
            <div className="row">
              <button className="primary" onClick={() => respond(open.id, "accept")}><Icon name="unlock" size={16} />Принять и открыть контакты</button>
              <button onClick={() => respond(open.id, "decline")}>Отклонить</button>
            </div>
          ) : open.status === "DECLINED" ? <p className="muted">Вы отклонили приглашение. Ваши контакты остались скрыты.</p>
            : <p className="ok">Вы приняли приглашение — работодатель теперь видит ваши контакты.</p>}
          {(open.status === "SENT" || open.status === "VIEWED") && <p className="muted" style={{ fontSize: 13 }}>Открытие контактов происходит только если вы нажмёте «Принять и открыть контакты».</p>}
        </Card>
      ) : (
        <Empty icon="eye" title="Выберите приглашение">Откройте приглашение из списка: увидите зарплатную вилку, условия и сообщение работодателя. Контакты остаются скрытыми, пока вы не согласитесь.</Empty>
      )}
    </div>
  );
}
