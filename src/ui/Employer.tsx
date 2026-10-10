import { useCallback, useEffect, useState } from "react";
import { api, type Session } from "./api";
import { EmployerFit } from "./TeamFit";
import type { Catalog, Fit, Invitation, MatchRow, Need, PublicCandidate } from "./types";
import {
  Badge, Card, ContactBox, Empty, ErrorBox, FitBlock, FORMAT_RU, GRADE_RU, Loading, SalaryBanner, salaryRange, SALARY_TYPE_RU, skillName,
  STATUS_RU, VerificationBadge, subLabel, gradeLine, InviteBadge, OPEN_INVITE } from "./ui";

interface Detail extends PublicCandidate { compat?: { reverse_fit: number | null; why: { text: string }[]; gaps: { text: string }[] }; fit: Fit | null; contact_status: "LOCKED" | "UNLOCKED"; contacts?: { full_name: string; email: string; phone: string | null } }
interface MatchResponse {
  run_id: number; candidates_considered: number; matched_total: number; excluded_summary: Record<string, number>; results: MatchRow[];
}

const EXCLUSION_RU: Record<string, string> = {
  SALARY_MISMATCH: "зарплатные ожидания выше бюджета", WORK_FORMAT_MISMATCH: "не подходит формат работы",
  GRADE_OUT_OF_RANGE: "уровень вне допуска (±1 подуровень)", SPECIALIZATION_MISMATCH: "другая специализация",
  NOT_VISIBLE: "профиль скрыт", NOT_OPEN_TO_INVITATIONS: "не принимает приглашения", LOCATION_MISMATCH: "другая локация",
  AVAILABILITY_MISMATCH: "не готов выйти в срок", GRADE_UNKNOWN: "грейд не указан",
};

export default function EmployerApp({ session }: { session: Session }) {
  const [tab, setTab] = useState<"match" | "pool" | "fit" | "invitations">("match");
  const [detail, setDetail] = useState<{ id: number; need: Need | null } | null>(null);
  const open = (id: number, need: Need | null) => { setDetail({ id, need }); window.scrollTo?.({ top: 0 }); };
  const tabs: [typeof tab, string][] = [["match", "Подбор по потребности"], ["pool", "Весь пул кандидатов"], ["fit", "Избранное и рекомендации"], ["invitations", "Отправленные приглашения"]];
  return (
    <>
      <h2 className="section-title">Кабинет работодателя</h2>
      <nav className="tabs" aria-label="Работодатель">
        {tabs.map(([k, l]) => <button key={k} className={tab === k ? "tab active" : "tab"} onClick={() => { setTab(k); setDetail(null); }}>{l}</button>)}
      </nav>
      {detail && <CandidatePanel session={session} id={detail.id} need={detail.need} close={() => setDetail(null)} />}
      {tab === "match" && <MatchTab session={session} open={open} />}
      {tab === "pool" && <PoolTab session={session} open={(id) => open(id, null)} />}
      {tab === "fit" && <EmployerFit session={session} open={open} />}
      {tab === "invitations" && <SentTab session={session} open={(id) => open(id, null)} />}
    </>
  );
}

async function download(session: Session, runId: number, format: "csv" | "json"): Promise<void> {
  const r = await fetch(`/api/employer/match-runs/${runId}/export?format=${format}`, { headers: { authorization: `Bearer ${session.token}` } });
  if (!r.ok) return;
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `fsp-match-run-${runId}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

function MatchTab({ session, open }: { session: Session; open: (id: number, need: Need | null) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [needs, setNeeds] = useState<Need[]>([]);
  const [need, setNeed] = useState<Need | null>(null);
  const [res, setRes] = useState<MatchResponse | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ title: "Python Backend (FastAPI)", grade: "MIDDLE", sub: "M2", req: ["api_fastapi", "postgresql"], opt: ["kafka", "docker_basics"],
    from: "200000", to: "250000", type: "GROSS", formats: ["REMOTE"], location: "", start: "", description: "Удалённая команда Python-бэкенда" });
  useEffect(() => {
    Promise.all([api<Catalog>("/api/catalog"), api<Need[]>("/api/employer/needs", { token: session.token })])
      .then(([c, n]) => { setCatalog(c); setNeeds(n); }).catch((e: Error) => setErr(e.message));
  }, [session.token]);
  const run = useCallback(async (n: Need) => {
    setBusy(true); setErr(""); setNeed(n); setShowAll(false);
    try { setRes(await api<MatchResponse>(`/api/employer/needs/${n.id}/match?limit=20`, { token: session.token, method: "POST" })); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }, [session.token]);
  const create = async () => {
    setErr(""); setBusy(true);
    try {
      const n = await api<Need>("/api/employer/needs", { token: session.token, body: {
        title: f.title, target_grade: f.grade, target_sublevel: f.sub || null, required_skills: f.req, optional_skills: f.opt,
        salary_from: Number(f.from), salary_to: Number(f.to), salary_type: f.type, work_formats: f.formats,
        location: f.location || null, max_start_days: f.start ? Number(f.start) : null, description: f.description } });
      setNeeds([...needs, n]); await run(n);
    } catch (e) { setErr((e as Error).message); setBusy(false); }
  };
  if (!catalog) return err ? <ErrorBox message={err} /> : <Loading />;
  const toggle = (key: "req" | "opt" | "formats", v: string) => setF({ ...f, [key]: f[key].includes(v) ? f[key].filter((x) => x !== v) : [...f[key], v] });
  const rows = res ? (showAll ? res.results : res.results.slice(0, 5)) : [];
  return (
    <div className="grid">
      <Card title="Потребность работодателя">
        <label>Роль *<input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></label>
        <div className="row">
          <label>Грейд *<select value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value, sub: catalog.grades[e.target.value][1] })}>
            {Object.entries(GRADE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Подуровень<select value={f.sub} onChange={(e) => setF({ ...f, sub: e.target.value })}>
            <option value="">любой</option>{catalog.grades[f.grade].map((s) => <option key={s} value={s}>{subLabel(s)}</option>)}</select></label>
        </div>
        <fieldset><legend>Обязательные навыки *</legend>
          {catalog.skills.map((s) => <label key={s.code} className="check"><input type="checkbox" checked={f.req.includes(s.code)} disabled={f.opt.includes(s.code)} onChange={() => toggle("req", s.code)} />{skillName(s.code, s.name)}{!s.verifiable && <span className="muted"> (опыт)</span>}</label>)}
        </fieldset>
        <fieldset><legend>Желательные навыки</legend>
          {catalog.skills.map((s) => <label key={s.code} className="check"><input type="checkbox" checked={f.opt.includes(s.code)} disabled={f.req.includes(s.code)} onChange={() => toggle("opt", s.code)} />{skillName(s.code, s.name)}</label>)}
        </fieldset>
        <div className="row">
          <label>Зарплата от, ₽<input inputMode="numeric" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value.replace(/\D/g, "") })} /></label>
          <label>до, ₽<input inputMode="numeric" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value.replace(/\D/g, "") })} /></label>
          <label>Тип<select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
        </div>
        <fieldset><legend>Формат работы</legend>
          {Object.entries(FORMAT_RU).map(([k, v]) => <label key={k} className="check"><input type="checkbox" checked={f.formats.includes(k)} onChange={() => toggle("formats", k)} />{v}</label>)}
        </fieldset>
        <div className="row">
          <label>Город (для офиса/гибрида)<input value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></label>
          <label>Выход не позже, дней<input inputMode="numeric" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value.replace(/\D/g, "") })} /></label>
        </div>
        <button className="primary" disabled={busy || f.req.length === 0 || f.formats.length === 0} onClick={create}>Подобрать кандидатов</button>
        {needs.length > 0 && (
          <div><h4>Ваши потребности</h4>{needs.map((n) => <button key={n.id} className="link" onClick={() => run(n)}>{n.title} · {salaryRange(n.salary_from, n.salary_to, n.salary_type)}</button>)}</div>
        )}
        {err && <ErrorBox message={err} />}
      </Card>
      <div>
        {busy && <Loading what="Подбираем" />}
        {!res && !busy && <Empty>Опишите потребность — получите небольшой объяснимый список кандидатов: почему подходит и какие пробелы.</Empty>}
        {res && need && (
          <>
            <Card title={`Подбор: ${need.title}`}>
              <p>Рассмотрено кандидатов: {res.candidates_considered}. Обязательные ограничения прошли: {res.matched_total}.</p>
              <p className="row">Экспорт в ATS (без контактов):
                <button className="link" onClick={() => void download(session, res.run_id, "csv")}>CSV</button>
                <button className="link" onClick={() => void download(session, res.run_id, "json")}>JSON</button></p>
              {Object.keys(res.excluded_summary).length > 0 && (
                <details><summary>Отсеяно по обязательным ограничениям</summary>
                  <ul>{Object.entries(res.excluded_summary).map(([k, v]) => <li key={k}>{EXCLUSION_RU[k] ?? k}: {v}</li>)}</ul></details>)}
            </Card>
            {res.results.length === 0 && <Empty>Подходящих кандидатов нет. Попробуйте расширить вилку или формат работы.</Empty>}
            {rows.map((r) => (
              <Card key={r.candidate.candidate_id} title={`#${r.rank} ${r.candidate.display_name}`} aside={<VerificationBadge status={r.candidate.verification_status} />}>
                <p className="muted">{gradeLine(r.candidate)}
                  {r.candidate.has_fsp && <> · <Badge tone="info">достижения ФСП (демо-данные)</Badge></>} · <InviteBadge status={r.candidate.invitation_status} /></p>
                <div className="chips">{(r.candidate.skills ?? []).filter((s) => s.verified_level).slice(0, 4).map((s) => <Badge key={s.skill} tone="ok">{skillName(s.skill)}: подтверждено</Badge>)}{(r.candidate.work_experience ?? []).length > 0 && <Badge tone="muted">опыт: {r.candidate.work_experience!.length} (заявлен)</Badge>}</div>
                <FitBlock label={r.requirement_fit_label} fit={r.requirement_fit} why={r.why} gaps={r.gaps} />
                <button className="primary" onClick={() => open(r.candidate.candidate_id, need)}>Открыть кандидата</button>
              </Card>))}
            {!showAll && res.results.length > 5 && <button onClick={() => setShowAll(true)}>Показать ещё ({res.results.length - 5})</button>}
          </>
        )}
      </div>
    </div>
  );
}

function CandidatePanel({ session, id, need, close }: { session: Session; id: number; need: Need | null; close: () => void }) {
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState<Invitation | null>(null);
  const load = useCallback(() => {
    api<Detail>(`/api/employer/candidates/${id}${need ? `?need_id=${need.id}` : ""}`, { token: session.token }).then(setD).catch((e: Error) => setErr(e.message));
  }, [id, need, session.token]);
  useEffect(load, [load]);
  if (err) return <Card title="Кандидат"><ErrorBox message={err} /><button onClick={close}>Закрыть</button></Card>;
  if (!d) return <Loading what="Открываем кандидата" />;
  const fit = d.fit && d.fit.eligible ? d.fit : null;
  return (
    <Card title={d.display_name} aside={<><VerificationBadge status={d.verification_status} /><button onClick={close}>Закрыть</button></>}>
      <p className="muted">{gradeLine(d)} · {d.work_formats.map((x) => FORMAT_RU[x] ?? x).join(", ")}{d.location && ` · ${d.location}`}
        {d.salary_expectation && ` · ожидания от ${d.salary_expectation.min.toLocaleString("ru-RU")} ₽ ${d.salary_expectation.type}`}</p>
      <p><InviteBadge status={d.invitation_status} /></p>
      {d.verification_status !== "VERIFIED" && <p className="warn">Грейд кандидата не подтверждён основной оценкой — в подборе он учитывается с понижением.</p>}
      {d.fit && !d.fit.eligible && <p className="warn">Не проходит обязательные ограничения этой потребности: {d.fit.exclusions?.map((x) => EXCLUSION_RU[x] ?? x).join(", ")}.</p>}
      {fit && fit.requirement_fit !== undefined && <FitBlock label={fit.requirement_fit_label ?? ""} fit={fit.requirement_fit} why={fit.why ?? []} gaps={fit.gaps ?? []} />}
      {d.compat && (
        <>
          <h4>Ожидания кандидата и вакансия {d.compat.reverse_fit !== null && <Badge tone="info">{Math.round(d.compat.reverse_fit * 100)}%</Badge>}</h4>
          <ul>{d.compat.why.map((r, i) => <li key={i} className="ok">{r.text}</li>)}{d.compat.gaps.map((r, i) => <li key={i} className="warn">{r.text}</li>)}</ul>
          {d.compat.why.length + d.compat.gaps.length === 0 && <p className="muted">Кандидат не указал интересы и цели — оценить ожидания нельзя.</p>}
        </>)}
      <h4>Навыки и подтверждения</h4>
      {d.skills.length === 0 ? <Empty>Подтверждённых навыков нет.</Empty> : (
        <table className="table"><thead><tr><th>Навык</th><th>Подтверждение</th></tr></thead><tbody>
          {d.skills.map((s) => (
            <tr key={s.skill}><td>{skillName(s.skill)}</td><td>
              {s.verified_level ? <Badge tone="ok">подтверждено оценкой: {GRADE_RU[s.verified_level]}</Badge> : s.claimed_only ? <Badge tone="muted">только заявлено</Badge> : null}
              {s.has_professional_experience && <Badge tone="muted">опыт (не подтверждён)</Badge>}
              {s.fsp_achievements.map((a) => <Badge key={a} tone="info">ФСП (демо): {a}</Badge>)}</td></tr>))}
        </tbody></table>)}
      {d.work_experience && d.work_experience.length > 0 && (
        <>
          <h4>Заявленный опыт работы <Badge tone="muted">не подтверждён</Badge></h4>
          <ul>{d.work_experience.map((e, i) => (
            <li key={i}>{e.position}, {e.company} · {e.start_date} — {e.end_date ?? "по настоящее время"}{e.stack.length > 0 && ` · ${e.stack.map((s) => skillName(s)).join(", ")}`}</li>))}</ul>
        </>)}
      {!d.has_fsp && <p className="muted">Истории ФСП нет — это не снижает грейд кандидата.</p>}
      <FavoriteButton session={session} candidateId={d.candidate_id} needId={need?.id ?? null} />
      <ContactBox unlocked={d.contact_status === "UNLOCKED"} contacts={d.contacts} />
      {sent ? <p className="ok" role="status">Приглашение отправлено ({STATUS_RU[sent.status]}). Открытие контактов — только после согласия кандидата.</p>
        : d.invitation_status && OPEN_INVITE.includes(d.invitation_status)
          ? <p className="muted">Приглашение этому кандидату уже отправлено ({STATUS_RU[d.invitation_status] ?? d.invitation_status}) — повторно приглашать нельзя, пока оно активно.</p>
          : <InviteForm session={session} candidateId={d.candidate_id} need={need} declined={d.invitation_status === "DECLINED"} done={(i) => { setSent(i); load(); }} />}
    </Card>
  );
}

function FavoriteButton({ session, candidateId, needId }: { session: Session; candidateId: number; needId: number | null }) {
  const [msg, setMsg] = useState("");
  const [note, setNote] = useState("");
  const save = async () => {
    try { await api("/api/employer/favorites", { token: session.token, body: { candidate_id: candidateId, need_id: needId, note } }); setMsg("Сохранено в избранное. Кандидат ничего не получает."); }
    catch (e) { setMsg((e as Error).message); }
  };
  return (
    <div className="row">
      <input placeholder="Заметка (необязательно)" value={note} onChange={(e) => setNote(e.target.value)} />
      <button onClick={save}>★ В избранное</button>
      {msg && <span role="status">{msg}</span>}
    </div>
  );
}

function InviteForm({ session, candidateId, need, declined, done }: { session: Session; candidateId: number; need: Need | null; declined: boolean; done: (i: Invitation) => void }) {
  const [needs, setNeeds] = useState<Need[]>([]);
  const [mode, setMode] = useState<"need" | "custom">(need ? "need" : "custom");
  const [needId, setNeedId] = useState<number | null>(need?.id ?? null);
  const [f, setF] = useState({ role: "", tasks: "", reqs: "", terms: "", from: "", to: "", type: "", format: "REMOTE", message: "Здравствуйте! Нам интересен ваш подтверждённый опыт." });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const applyNeed = useCallback((n: Need) => {  // тип зарплаты и вилка переносятся из потребности; дальше можно править вручную
    setNeedId(n.id);
    setF((p) => ({ ...p, role: n.title, from: String(n.salary_from), to: String(n.salary_to), type: n.salary_type,
      format: n.work_formats[0] ?? p.format, tasks: p.tasks || (n.description ?? "") }));
  }, []);
  useEffect(() => { api<Need[]>("/api/employer/needs", { token: session.token }).then(setNeeds).catch(() => undefined); }, [session.token]);
  useEffect(() => { if (need) applyNeed(need); }, [need, applyNeed]);
  const chosen = needs.find((n) => n.id === needId) ?? (need && need.id === needId ? need : null);
  const set = (k: keyof typeof f, v: string) => setF({ ...f, [k]: v });
  const missing: string[] = [];
  if (mode === "need" && needId === null) missing.push("выберите потребность или переключитесь на самостоятельное предложение");
  if (!f.role.trim()) missing.push("укажите должность");
  if (f.tasks.trim().length < 5) missing.push("опишите задачи");
  if (f.reqs.trim().length < 5) missing.push("опишите требования");
  if (f.terms.trim().length < 5) missing.push("опишите условия работы");
  if (!f.from || !f.to) missing.push("укажите зарплатную вилку");
  else if (Number(f.to) < Number(f.from)) missing.push("«до» не может быть меньше «от»");
  if (!f.type) missing.push("выберите тип зарплаты (GROSS или NET)");
  if (!f.message.trim()) missing.push("напишите сообщение кандидату");
  const description = `Задачи:\n${f.tasks.trim()}\n\nТребования:\n${f.reqs.trim()}\n\nУсловия:\n${f.terms.trim()}`;
  const send = async () => {
    if (missing.length || busy) return;  // защита от обхода disabled; сервер проверяет всё повторно
    setErr(""); setBusy(true);
    try {
      done(await api<Invitation>("/api/employer/invitations", { token: session.token, body: {
        candidate_id: candidateId, need_id: mode === "need" ? needId : null, role: f.role.trim(), description, salary_from: Number(f.from),
        salary_to: Number(f.to), salary_type: f.type, work_format: f.format, message: f.message.trim() } }));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const typeChanged = mode === "need" && chosen && f.type && f.type !== chosen.salary_type;
  return (
    <div className="invite">
      <h4>Приглашение с зарплатой</h4>
      {declined && <p className="muted">Кандидат ранее отклонил приглашение — можно отправить новое предложение с другими условиями.</p>}
      <div className="row">
        <button className={mode === "need" ? "tab active" : "tab"} onClick={() => setMode("need")}>По потребности</button>
        <button className={mode === "custom" ? "tab active" : "tab"} onClick={() => { setMode("custom"); setNeedId(null); }}>Самостоятельное предложение</button>
      </div>
      {mode === "need" && (
        <label>Потребность *<select value={needId ?? ""} onChange={(e) => { const n = needs.find((x) => x.id === Number(e.target.value)); if (n) applyNeed(n); else setNeedId(null); }}>
          <option value="">выберите…</option>{needs.map((n) => <option key={n.id} value={n.id}>{n.title}</option>)}</select></label>)}
      <div className="row">
        <label>Должность *<input value={f.role} onChange={(e) => set("role", e.target.value)} /></label>
        <label>Формат<select value={f.format} onChange={(e) => set("format", e.target.value)}>{Object.entries(FORMAT_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      </div>
      <label>Задачи *<textarea rows={2} placeholder="Чем предстоит заниматься" value={f.tasks} onChange={(e) => set("tasks", e.target.value)} /></label>
      <label>Требования *<textarea rows={2} placeholder="Стек, опыт, что важно" value={f.reqs} onChange={(e) => set("reqs", e.target.value)} /></label>
      <label>Условия *<textarea rows={2} placeholder="График, команда, оформление, бонусы" value={f.terms} onChange={(e) => set("terms", e.target.value)} /></label>
      <div className="row">
        <label>Зарплата от, ₽ *<input inputMode="numeric" value={f.from} onChange={(e) => set("from", e.target.value.replace(/\D/g, ""))} /></label>
        <label>до, ₽ *<input inputMode="numeric" value={f.to} onChange={(e) => set("to", e.target.value.replace(/\D/g, ""))} /></label>
        <label>Тип зарплаты *<select value={f.type} onChange={(e) => set("type", e.target.value)}><option value="">выберите…</option><option value="GROSS">{SALARY_TYPE_RU.GROSS}</option><option value="NET">{SALARY_TYPE_RU.NET}</option></select></label>
      </div>
      {typeChanged && <p className="muted">Тип зарплаты изменён вручную: в потребности указано «{SALARY_TYPE_RU[chosen!.salary_type]}».</p>}
      <label>Сообщение *<textarea rows={2} value={f.message} onChange={(e) => set("message", e.target.value)} /></label>
      <p className="muted">Зарплатная вилка и тип зарплаты обязательны — сервер не примет приглашение без них. Контакты кандидата откроются только после его согласия.</p>
      {missing.length > 0 && <ul className="warn" aria-label="Что нужно заполнить">{missing.map((m) => <li key={m}>{m}</li>)}</ul>}
      <button className="primary" disabled={missing.length > 0 || busy} onClick={send}>Отправить приглашение</button>
      {err && <ErrorBox message={err} />}
    </div>
  );
}

function PoolTab({ session, open }: { session: Session; open: (id: number) => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [q, setQ] = useState({ grade: "", sublevel: "", verification: "", skill: "", has_fsp: "", work_format: "", location: "", salary_max: "" });
  const [res, setRes] = useState<{ total: number; candidates: PublicCandidate[] } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Catalog>("/api/catalog").then(setCatalog).catch((e: Error) => setErr(e.message)); }, []);
  const search = useCallback(() => {
    const p = new URLSearchParams({ limit: "100" });
    Object.entries(q).forEach(([k, v]) => { if (v) p.set(k, v); });
    api<{ total: number; candidates: PublicCandidate[] }>(`/api/employer/pool?${p}`, { token: session.token }).then(setRes).catch((e: Error) => setErr(e.message));
  }, [q, session.token]);
  useEffect(search, [search]);
  const sel = (k: keyof typeof q, opts: [string, string][], label: string) => (
    <label>{label}<select value={q[k]} onChange={(e) => setQ({ ...q, [k]: e.target.value, ...(k === "grade" ? { sublevel: "" } : {}) })}><option value="">любой</option>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>);
  return (
    <div className="grid">
      <Card title="Фильтры">
        {sel("grade", Object.entries(GRADE_RU), "Подтверждённый грейд платформы")}
        {sel("sublevel", (q.grade && catalog ? catalog.grades[q.grade] : ["J1", "J2", "J3", "M1", "M2", "M3", "S1", "S2", "S3"]).map((s) => [s, subLabel(s)]), "Подуровень (подтверждён тестом)")}
        {sel("verification", [["VERIFIED", "Подтверждено"], ["NOT_VERIFIED", "Не подтверждено"], ["UNVERIFIED", "Оценка не пройдена"]], "Статус подтверждения")}
        {catalog && sel("skill", catalog.skills.map((s) => [s.code, skillName(s.code, s.name)]), "Подтверждённый навык")}
        {sel("has_fsp", [["true", "есть"], ["false", "нет"]], "Достижения ФСП")}
        {sel("work_format", Object.entries(FORMAT_RU), "Формат работы")}
        <label>Город<input value={q.location} onChange={(e) => setQ({ ...q, location: e.target.value })} /></label>
        <label>Ожидания не выше, ₽<input inputMode="numeric" value={q.salary_max} onChange={(e) => setQ({ ...q, salary_max: e.target.value.replace(/\D/g, "") })} /></label>
      </Card>
      <div>
        {err && <ErrorBox message={err} />}
        {!res ? <Loading /> : (<>
          <p className="muted">Найдено: {res.total}. Контакты кандидатов скрыты до их согласия (открытие контактов — только после принятия приглашения).</p>
          {res.candidates.length === 0 && <Empty>По этим фильтрам никого нет.</Empty>}
          {res.candidates.map((c) => (
            <Card key={c.candidate_id} title={c.display_name} aside={<VerificationBadge status={c.verification_status} />}>
              <p className="muted">{gradeLine(c)}
                {c.has_fsp ? " · ФСП (демо)" : ""}{c.salary_expectation ? ` · от ${c.salary_expectation.min.toLocaleString("ru-RU")} ₽ ${c.salary_expectation.type}` : ""} · <InviteBadge status={c.invitation_status} /></p>
              <div className="chips">{(c.skills ?? []).filter((s) => s.verified_level).slice(0, 4).map((s) => <Badge key={s.skill} tone="ok">{skillName(s.skill)}: подтверждено</Badge>)}{(c.work_experience ?? []).length > 0 && <Badge tone="muted">опыт: {c.work_experience!.length} (заявлен)</Badge>}</div>
                <button onClick={() => open(c.candidate_id)}>Открыть</button>
            </Card>))}
        </>)}
      </div>
    </div>
  );
}

function SentTab({ session, open }: { session: Session; open: (id: number) => void }) {
  const [list, setList] = useState<Invitation[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => { api<Invitation[]>("/api/employer/invitations", { token: session.token }).then(setList).catch((e: Error) => setErr(e.message)); }, [session.token]);
  useEffect(load, [load]);
  if (err) return <ErrorBox message={err} />;
  if (!list) return <Loading />;
  return (
    <div>
      <button onClick={load}>Обновить статусы</button>
      {list.length === 0 ? <Empty>Вы ещё не отправляли приглашений. Откройте кандидата из подбора и отправьте предложение с зарплатой.</Empty> : list.map((i) => (
        <Card key={i.id} title={`${i.candidate?.display_name ?? "Кандидат"} — ${i.role}`} aside={<Badge tone={i.status === "DECLINED" ? "bad" : i.contacts_unlocked ? "ok" : "info"}>{STATUS_RU[i.status]}</Badge>}>
          {i.candidate && <p className="muted">{gradeLine(i.candidate)}</p>}
          <SalaryBanner from={i.salary_from} to={i.salary_to} type={i.salary_type} />
          {i.description && <details><summary>Описание предложения</summary><p style={{ whiteSpace: "pre-wrap" }}>{i.description}</p></details>}
          {i.candidate_id !== undefined && <button onClick={() => open(i.candidate_id!)}>Открыть карточку кандидата</button>}
          <ContactBox unlocked={!!i.contacts_unlocked} contacts={i.contacts} />
        </Card>))}
    </div>
  );
}
