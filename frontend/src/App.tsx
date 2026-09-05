import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components';
import { Overview, Decisions, Policy, Ask } from './pages';
import { ModeProvider } from './context/ModeContext';
import './styles/globals.css';

function App() {
  return (
    <ModeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="decisions" element={<Decisions />} />
            <Route path="policy" element={<Policy />} />
            <Route path="ask" element={<Ask />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ModeProvider>
  );
}

export default App;
