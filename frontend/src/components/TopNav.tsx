import { NavLink } from 'react-router-dom';
import { useState } from 'react';
import './TopNav.css';

const NAV_ITEMS = [
  { path: '/', label: 'Overview' },
  { path: '/decisions', label: 'Decisions' },
  { path: '/policy', label: 'Policy' },
  { path: '/ask', label: 'Ask REVEN' },
];

export function TopNav() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  return (
    <header className="topnav">
      <div className="topnav-inner">
        {/* Brand */}
        <NavLink to="/" className="topnav-brand">
          <svg
            className="topnav-mark"
            viewBox="0 0 28 28"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            {/* Feedback loop mark: circle with directional gap */}
            <circle
              cx="14"
              cy="14"
              r="10"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeDasharray="50 13"
              strokeDashoffset="-8"
              strokeLinecap="round"
            />
            {/* Arrow head pointing right — completing the loop */}
            <path
              d="M22.5 9.5L26 14L22.5 18.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="topnav-wordmark">reven</span>
        </NavLink>

        {/* Primary navigation */}
        <nav className="topnav-links" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `topnav-link${isActive ? ' topnav-link--active' : ''}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Right cluster */}
        <div className="topnav-right">
          {/* Search */}
          <div className={`topnav-search${searchOpen ? ' topnav-search--open' : ''}`}>
            {searchOpen ? (
              <>
                <input
                  type="search"
                  className="topnav-search-input"
                  placeholder="Search customer ID…"
                  value={searchValue}
                  onChange={(e) => setSearchValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      setSearchOpen(false);
                      setSearchValue('');
                    }
                  }}
                  autoFocus
                />
                <button
                  className="topnav-icon-btn"
                  onClick={() => {
                    setSearchOpen(false);
                    setSearchValue('');
                  }}
                  aria-label="Close search"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round"/>
                  </svg>
                </button>
              </>
            ) : (
              <button
                className="topnav-icon-btn"
                onClick={() => setSearchOpen(true)}
                aria-label="Search"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <circle cx="11" cy="11" r="7"/>
                  <path d="M21 21l-4.35-4.35"/>
                </svg>
              </button>
            )}
          </div>

          {/* Health indicator */}
          <div className="topnav-health" title="System healthy">
            <span className="status-dot status-dot--revenue" />
          </div>
        </div>
      </div>
    </header>
  );
}
