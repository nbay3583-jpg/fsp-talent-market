import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Session } from "./api";
import type { Catalog, Invitation } from "./types";
import {
  Badge, Card, Empty, ErrorBox, FORMAT_RU, GRADE_RU, Loading, SALARY_TYPE_RU, SalaryBanner, skillName, STATUS_RU, VerificationBadge,
} from "./ui";
import { ContactBox } from "./ui";

interface Me {
  id: number; full_name: string; email: string; phone: string | null; specialization: string | null;
  claimed_grade: string | null; verification_status: string; verified_grade: string | null;
  preferences: {
    salary_min: number | null; salary_type: string | null; work_formats: string[]; location: string | null;
    available_in_days: number | null; profile_visible: boolean; open_to_invitations: boolean;
  };
}
interface Task { variant_id: number; competency: string; prompt: string; options: Record<string, string> }
interface Result {
  verification_status: string; claimed_grade: string; target_grade: string; achieved_sublevel: string | null;
  score: number; competency_scores: Record<string, number>;
}
interface Profile {
  specialization: string | null; claimed_grade: string | null; verification_status: string;
  verified_grade: string | null; verified_sublevel: string | null;
  assessment: { target_grade: string; verification_status: string; achieved_sublevel: string | null; score: number; competency_scores: Record<string, number>; scored_at: string | null } | null;
  skills: {
    skill: string; name: string; claimed_level: string | null; claim_source: string; verified_level: string | null;
    verified_sublevel: string | null;
    evidence: { type: string; strength: string; level: string | null; title: string | null }[];
  }[];
  fsp: { has_history: boolean; evidence_items: number };
}

const EVIDENCE_RU: Record<string, string> = {
  CORE_ASSESSMENT: "Основная оценка компетенций", TECHNOLOGY_ASSESSMENT: "Оценка по технологии",
  PROFESSIONAL_EXPERIENCE: "Профессиональный опыт", FSP_ACHIEVEMENT: "Достижение ФСП", RECENT_CHALLENGE: "Свежее задание",
};
const STRENGTH_RU: Record<string, string> = { HIGH: "высокая", MEDIUM: "средняя", LOW: "низкая" };
const SOURCE_RU: Record<string, string> = {
  self_reported: "заявлено кандидатом", core_assessment: "создано тестом", fsp: "из данных ФСП", experience: "опыт",
};

export default function CandidateApp({ session, demoMode }: { session: Session; demoMode: boolean }) {
  const [tab, setTab] = useState<"profile" | "test" | "evidence" | "invitations">("profile");
  const tabs: [typeof tab, string][] = [
    ["profile", "Профиль"], ["test", "Основная оценка"], ["evidence", "Профиль подтверждённых компетенций"], ["invitations", "Приглашения"],
  ];
  return (
    <>
      <h2 className="section-title">Кабинет кандидата</h2>
      <nav className="tabs" aria-label="Кандидат">
        {tabs.map(([k, label]) => (
          <button key={k} className={tab === k ? "tab active" : "tab"} onClick={() => setTab(k)}>{label}</button>
        ))}
      </nav>
      {tab === "profile" && <ProfileTab session={session} />}
      {tab === "test" && <AssessmentTab session={session} demoMode={demoMode} goEvidence={() => setTab("evidence")} />}
      {tab === "evidence" && <EvidenceTab session={session} />}
      {tab === "invitations" && <InvitationsTab session={session} />}
    </>
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
        profile_visible: form.visible, open_to_invitations: form.open } });
      setSaved(true);
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="grid">
      <Card title="Кандидат" aside={<VerificationBadge status={me.verification_status} />}>
        <p className="muted">Заявленный грейд — это заявка. Подтверждённый грейд платформы определяет только основная оценка компетенций: не резюме, не достижения ФСП и не вакансия.</p>
        <label>Имя<input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} /></label>
        <label>Email (виден только вам)<input value={me.email} disabled /></label>
        <label>Телефон (скрыт до вашего согласия)<input value={form.phone} onChange={(e) => set("phone", e.target.value)} /></label>
        <div className="row">
          <label>Специализация
            <select value={form.specialization} onChange={(e) => set("specialization", e.target.value)}>
              {catalog.specializations.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
          </label>
          <label>Желаемый грейд
            <select value={form.claimed_grade} onChange={(e) => set("claimed_grade", e.target.value)}>
              {Object.keys(catalog.grades).map((g) => <option key={g} value={g}>{GRADE_RU[g]}</option>)}
            </select>
          </label>
        </div>
        <p className="muted">Полная оценка реализована для Backend / Python.</p>
      </Card>
      <Card title="Предпочтения для подбора">
        <div className="row">
          <label>Минимальная зарплата, ₽<input inputMode="numeric" value={form.salary_min} onChange={(e) => set("salary_min", e.target.value.replace(/\D/g, ""))} /></label>
          <label>Тип<select value={form.salary_type} onChange={(e) => set("salary_type", e.target.value)}><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
        </div>
        <fieldset><legend>Формат работы</legend>
          {Object.entries(FORMAT_RU).map(([k, v]) => (
            <label key={k} className="check"><input type="checkbox" checked={form.formats.includes(k)} onChange={() => toggleFormat(k)} />{v}</label>
          ))}
        </fieldset>
        <div className="row">
          <label>Город<input value={form.location} onChange={(e) => set("location", e.target.value)} /></label>
          <label>Готов выйти через, дней<input inputMode="numeric" value={form.available_in_days} onChange={(e) => set("available_in_days", e.target.value.replace(/\D/g, ""))} /></label>
        </div>
        <label className="check"><input type="checkbox" checked={form.visible} onChange={(e) => set("visible", e.target.checked)} />Профиль виден работодателям (без контактов)</label>
        <label className="check"><input type="checkbox" checked={form.open} onChange={(e) => set("open", e.target.checked)} />Готов получать приглашения</label>
        <button className="primary" onClick={save}>Сохранить</button>
        {saved && <p className="ok" role="status">Сохранено</p>}
        {err && <ErrorBox message={err} />}
      </Card>
    </div>
  );
}

function AssessmentTab({ session, demoMode, goEvidence }: { session: Session; demoMode: boolean; goEvidence: () => void }) {
  const [grade, setGrade] = useState("MIDDLE");
  const [attempt, setAttempt] = useState<{ attempt_id: number; target_grade: string; tasks: Task[] } | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [started, setStarted] = useState<number | null>(null);
  const start = async () => {
    setErr(""); setResult(null); setBusy(true);
    try {
      const a = await api<{ attempt_id: number; target_grade: string; tasks: Task[] }>("/api/assessments", { token: session.token, body: { target_grade: grade } });
      setAttempt(a); setAnswers({}); setStarted(Date.now());
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 409 ? `Повторная попытка пока недоступна: ${e.message}` : (e as Error).message);
    } finally { setBusy(false); }
  };
  const fillReference = async () => {
    if (!attempt) return;
    const r = await api<{ answers: Record<string, string> }>(`/api/demo/assessments/${attempt.attempt_id}/reference-answers`, { token: session.token });
    setAnswers(Object.fromEntries(Object.entries(r.answers).map(([k, v]) => [Number(k), v])));
  };
  const submit = async () => {
    if (!attempt) return;
    setBusy(true); setErr("");
    try {
      const r = await api<Result>(`/api/assessments/${attempt.attempt_id}/submit`, { token: session.token, body: { answers } });
      setResult(r); setAttempt(null);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  if (result) return <ResultCard result={result} goEvidence={goEvidence} again={() => setResult(null)} />;
  if (!attempt) {
    return (
      <Card title="Основная оценка компетенций (Core Assessment): Backend / Python">
        <p>Короткая оценка (около 3–5 минут): Python, SQL, API/FastAPI, тестирование, Docker, системное мышление. Задания параметризованы: у каждого кандидата свои варианты с тем же уровнем сложности и теми же критериями. Оценка полностью детерминирована — без нейросетей.</p>
        <label>Грейд, который вы подтверждаете
          <select value={grade} onChange={(e) => setGrade(e.target.value)}>
            {Object.entries(GRADE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <button className="primary" disabled={busy} onClick={start}>Начать оценку</button>
        {err && <ErrorBox message={err} />}
      </Card>
    );
  }
  const done = attempt.tasks.every((t) => answers[t.variant_id]);
  const mins = started ? Math.max(0, Math.round((Date.now() - started) / 60000)) : 0;
  return (
    <div>
      <Card title={`Оценка ${GRADE_RU[attempt.target_grade]} · ${attempt.tasks.length} заданий`} aside={<span className="muted">{mins} мин</span>}>
        {demoMode && <button onClick={fillReference}>Демо: заполнить эталонными ответами</button>}
      </Card>
      {attempt.tasks.map((t, i) => (
        <Card key={t.variant_id} title={`${i + 1}. ${skillName(t.competency)}`}>
          <pre className="prompt">{t.prompt}</pre>
          {Object.entries(t.options).map(([k, v]) => (
            <label key={k} className="option">
              <input type="radio" name={`q${t.variant_id}`} checked={answers[t.variant_id] === k} onChange={() => setAnswers({ ...answers, [t.variant_id]: k })} />
              <b>{k}</b> <span>{v}</span>
            </label>
          ))}
        </Card>
      ))}
      <button className="primary" disabled={!done || busy} onClick={submit}>Отправить ответы</button>
      {!done && <p className="muted">Ответьте на все задания, чтобы отправить ответы.</p>}
      {err && <ErrorBox message={err} />}
    </div>
  );
}

function ResultCard({ result, goEvidence, again }: { result: Result; goEvidence: () => void; again: () => void }) {
  const ok = result.verification_status === "VERIFIED";
  return (
    <Card title="Результат основной оценки компетенций" aside={<VerificationBadge status={result.verification_status} />}>
      <p className="big">Backend / {GRADE_RU[result.target_grade]}{ok && result.achieved_sublevel ? ` (${result.achieved_sublevel})` : ""}</p>
      {ok ? (
        <p className="ok">Уровень подтверждён тестом. Он появился в вашем профиле подтверждённых компетенций.</p>
      ) : (
        <p>
          Грейд <b>{GRADE_RU[result.claimed_grade]}</b> пока не подтверждён. Заявленный грейд {GRADE_RU[result.claimed_grade]} сохраняется (не подтверждён) — платформа не понижает вас автоматически до Junior.
          Можно пройти повторную попытку после паузы или оценку другого грейда.
        </p>
      )}
      <table className="table"><thead><tr><th>Компетенция</th><th>Результат</th></tr></thead>
        <tbody>{Object.entries(result.competency_scores).map(([k, v]) => <tr key={k}><td>{skillName(k)}</td><td>{Math.round(v * 100)}%</td></tr>)}</tbody></table>
      <div className="row"><button className="primary" onClick={goEvidence}>Открыть профиль подтверждённых компетенций</button><button onClick={again}>Закрыть</button></div>
    </Card>
  );
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
  return (
    <div>
      <Card title="Профиль подтверждённых компетенций" aside={<VerificationBadge status={p.verification_status} />}>
        <p className="big">Backend / {p.claimed_grade ? GRADE_RU[p.claimed_grade] : "—"} (заявлено)
          {p.verified_grade && <> · <Badge tone="ok">подтверждено: {GRADE_RU[p.verified_grade]} {p.verified_sublevel}</Badge></>}</p>
        {p.verification_status === "NOT_VERIFIED" && <p>Заявленный грейд не подтверждён. Он сохранён — платформа не заменяет его более низким.</p>}
        {p.verification_status === "UNVERIFIED" && <p className="muted">Пройдите основную оценку компетенций, чтобы подтвердить грейд.</p>}
        <p className="muted">Здесь нет единого «рейтинга кандидата»: только заявки и то, чем они подтверждены.</p>
      </Card>
      {p.skills.length === 0 ? <Empty>Подтверждённых навыков пока нет. Заявки без подтверждения ничего не меняют.</Empty> : (
        <Card title="Навыки: заявка → подтверждение">
          <table className="table"><thead><tr><th>Навык</th><th>Заявка</th><th>Подтверждение</th><th>Подтверждённый грейд платформы</th></tr></thead>
            <tbody>{p.skills.map((s) => (
              <tr key={s.skill}>
                <td><b>{skillName(s.skill, s.name)}</b></td>
                <td>{s.claimed_level ? GRADE_RU[s.claimed_level] : "—"}<br /><span className="muted">{SOURCE_RU[s.claim_source] ?? s.claim_source}</span></td>
                <td>{s.evidence.length === 0 ? <span className="muted">нет подтверждений</span> : s.evidence.map((e, i) => (
                  <div key={i}><Badge tone={e.type === "FSP_ACHIEVEMENT" ? "info" : "ok"}>{EVIDENCE_RU[e.type] ?? e.type}</Badge> сила: {STRENGTH_RU[e.strength] ?? e.strength}{e.title ? ` · ${e.title}` : ""}</div>
                ))}</td>
                <td>{s.verified_level ? <Badge tone="ok">{GRADE_RU[s.verified_level]} {s.verified_sublevel}</Badge> : <Badge tone="muted">не подтверждён</Badge>}</td>
              </tr>))}</tbody></table>
        </Card>
      )}
      {p.assessment && (
        <Card title="Результат основной оценки">
          <p>{GRADE_RU[p.assessment.target_grade]}: <VerificationBadge status={p.assessment.verification_status} /> · {Math.round(p.assessment.score * 100)}% правильных ответов</p>
        </Card>
      )}
      <Card title="Достижения ФСП (внешнее подтверждение)">
        {p.fsp.has_history ? <p className="ok">Найдено подтверждений: {p.fsp.evidence_items}. Они привязаны к релевантным навыкам и не меняют ваш уровень.</p>
          : <Empty>Истории ФСП нет — это нормально. Отсутствие достижений не ухудшает ваш уровень и профиль.</Empty>}
        <div className="row"><input placeholder="ФСП ID, например FSP-1001" value={fsp} onChange={(e) => setFsp(e.target.value)} /><button onClick={link} disabled={!fsp}>Подключить ФСП ID (демо)</button></div>
        {fspMsg && <p role="status">{fspMsg}</p>}
      </Card>
    </div>
  );
}

function InvitationsTab({ session }: { session: Session }) {
  const [list, setList] = useState<Invitation[] | null>(null);
  const [open, setOpen] = useState<Invitation | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    api<Invitation[]>("/api/candidates/me/invitations", { token: session.token }).then(setList).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  useEffect(load, [load]);
  const view = async (id: number) => { setOpen(await api<Invitation>(`/api/candidates/me/invitations/${id}`, { token: session.token })); load(); };
  const respond = async (id: number, action: "accept" | "decline") => {
    try { setOpen(await api<Invitation>(`/api/candidates/me/invitations/${id}/${action}`, { token: session.token, method: "POST" })); load(); }
    catch (e) { setErr((e as Error).message); }
  };
  if (err) return <ErrorBox message={err} />;
  if (!list) return <Loading what="Загружаем приглашения" />;
  return (
    <div className="grid">
      <div>
        {list.length === 0 ? <Empty>Приглашений пока нет. Работодатели находят вас по подтверждённым навыкам и пишут адресно — с зарплатой.</Empty> :
          list.map((i) => (
            <Card key={i.id} title={`${i.company} — ${i.role}`} aside={<Badge tone={i.status === "DECLINED" ? "bad" : i.status.startsWith("ACC") || i.status === "CONTACTS_UNLOCKED" ? "ok" : "info"}>{STATUS_RU[i.status]}</Badge>}>
              <SalaryBanner from={i.salary_from} to={i.salary_to} type={i.salary_type} />
              <button onClick={() => view(i.id)}>Открыть</button>
            </Card>))}
      </div>
      {open && (
        <Card title={`${open.company} — ${open.role}`} aside={<Badge tone="info">{STATUS_RU[open.status]}</Badge>}>
          <SalaryBanner from={open.salary_from} to={open.salary_to} type={open.salary_type} />
          <p><b>Формат:</b> {FORMAT_RU[open.work_format] ?? open.work_format}</p>
          <p>{open.description}</p>
          <blockquote>{open.message}</blockquote>
          {(open.status === "SENT" || open.status === "VIEWED") ? (
            <div className="row">
              <button className="primary" onClick={() => respond(open.id, "accept")}>Принять и открыть контакты</button>
              <button onClick={() => respond(open.id, "decline")}>Отклонить</button>
            </div>
          ) : open.status === "DECLINED" ? <p className="muted">Вы отклонили приглашение. Ваши контакты остались скрыты.</p>
            : <p className="ok">Вы приняли приглашение — работодатель теперь видит ваши контакты.</p>}
          <p className="muted">Открытие контактов происходит только если вы нажмёте «Принять и открыть контакты».</p>
        </Card>
      )}
    </div>
  );
}
