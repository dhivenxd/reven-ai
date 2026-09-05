import { NavLink, Outlet } from 'react-router-dom';
import { useMode } from '../context/ModeContext';
import './Layout.css';

const NAV = [
  { to: '/', label: 'Overview', icon: 'grid' },
  { to: '/decisions', label: 'Decisions', icon: 'branch' },
  { to: '/policy', label: 'Policy', icon: 'shield' },
  { to: '/ask', label: 'Ask REVEN', icon: 'spark' },
];

function Icon({ name }: { name: string }) {
  const common = { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  if (name === 'grid') return <svg {...common}><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>;
  if (name === 'branch') return <svg {...common}><path d="M7 4v10a4 4 0 0 0 4 4h6"/><path d="M17 15l3 3-3 3"/><circle cx="7" cy="4" r="2"/><circle cx="7" cy="18" r="2"/></svg>;
  if (name === 'shield') return <svg {...common}><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/></svg>;
  return <svg {...common}><path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="8"/></svg>;
}

function Logo() {
  return (
    <NavLink to="/" className="brand" aria-label="REVEN overview">
      <span className="brand-mark"><span /><span /></span>
      <span>REVEN</span>
    </NavLink>
  );
}

export function Layout() {
  const { mode, setMode } = useMode();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Logo />
        <nav className="sidebar-nav" aria-label="Primary navigation">
          <div className="sidebar-label">Workspace</div>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="mode-label">Environment</div>
          <div className="mode-switch" role="group" aria-label="Environment mode">
            <button className={mode === 'demo' ? 'selected' : ''} onClick={() => setMode('demo')}>Demo</button>
            <button className={mode === 'merchant' ? 'selected' : ''} onClick={() => setMode('merchant')}>Merchant</button>
          </div>
          <div className={`connection-note ${mode}`}>
            <span className="connection-dot" />
            {mode === 'demo' ? 'Synthetic workspace' : 'Merchant integration'}
          </div>
          <div className="sidebar-footer">
            <span>REVEN</span>
            <span>Revenue intelligence</span>
          </div>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">Revenue intelligence <span>/</span> {mode === 'demo' ? 'Demo workspace' : 'Merchant workspace'}</div>
          <div className="topbar-right">
            <span className={`mode-pill ${mode}`}>{mode === 'demo' ? 'DEMO' : 'MERCHANT'}</span>
            <span className="system-status"><i /> System healthy</span>
          </div>
        </header>
        <div className="page-frame">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
