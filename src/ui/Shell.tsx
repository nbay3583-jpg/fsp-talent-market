import { useState, type ReactNode } from "react";
import { Icon, Logo } from "./ui";

export interface NavItem { key: string; label: string; icon: string; count?: number }
/** What App passes to a cabinet so it can render the shared frame. */
export interface ShellCtx { health: "checking" | "ok" | "unavailable"; demoMode: boolean; onLogout: () => void; onValidation: () => void; banners: ReactNode }
export interface ShellProps {
  items: NavItem[];
  active: string;
  onSelect: (key: string) => void;
  who: { role: string; label: string };
  health: "checking" | "ok" | "unavailable";
  demoMode: boolean;
  onLogout: () => void;
  onValidation: () => void;
  children: ReactNode;
}

const HEALTH_RU = { checking: "Проверка системы…", ok: "Система работает", unavailable: "Система недоступна" };

/** Dark-graphite cabinet frame: sidebar on desktop, drawer + top bar on mobile. */
export default function Shell(p: ShellProps) {
  const [open, setOpen] = useState(false);
  const pick = (k: string) => { p.onSelect(k); setOpen(false); };
  return (
    <div className="cabinet">
      <div className="mobile-bar">
        <Logo />
        <button className="icon-btn" aria-label={open ? "Закрыть меню" : "Открыть меню"} aria-expanded={open} onClick={() => setOpen(!open)}><Icon name={open ? "close" : "menu"} /></button>
      </div>
      <div className={`scrim${open ? " open" : ""}`} onClick={() => setOpen(false)} />
      <aside className={`side${open ? " open" : ""}`} aria-label="Меню кабинета">
        <Logo />
        <nav className="side-nav">
          {p.items.map((i) => (
            <button key={i.key} className={p.active === i.key ? "active" : ""} aria-current={p.active === i.key ? "page" : undefined} onClick={() => pick(i.key)}>
              <Icon name={i.icon} /><span>{i.label}</span>
              {i.count ? <span className="count">{i.count}</span> : null}
            </button>
          ))}
        </nav>
        <div className="side-foot">
          <div className="side-card"><b>{p.who.label}</b>{p.who.role}{p.demoMode ? " · демо-режим" : ""}</div>
          <span className={`health health-${p.health}`}>{HEALTH_RU[p.health]}</span>
          <div className="side-links">
            <button onClick={() => { p.onValidation(); setOpen(false); }}>Валидация</button>
            <a href="/docs" target="_blank" rel="noreferrer">API</a>
            <button onClick={p.onLogout}>Выйти</button>
          </div>
        </div>
      </aside>
      <main className="cabinet-main">{p.children}</main>
    </div>
  );
}
