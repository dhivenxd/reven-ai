import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type AppMode = 'demo' | 'merchant';

type ModeContextValue = {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
};

const ModeContext = createContext<ModeContextValue | null>(null);

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<AppMode>(() => {
    const saved = localStorage.getItem('reven-mode');
    return saved === 'merchant' ? 'merchant' : 'demo';
  });

  const setMode = (next: AppMode) => {
    setModeState(next);
    localStorage.setItem('reven-mode', next);
  };

  useEffect(() => {
    document.documentElement.dataset.mode = mode;
  }, [mode]);

  const value = useMemo(() => ({ mode, setMode }), [mode]);
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export function useMode() {
  const value = useContext(ModeContext);
  if (!value) throw new Error('useMode must be used inside ModeProvider');
  return value;
}
