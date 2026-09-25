import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';

function App() {
  return (
    <div>
      <Routes>
        {/* A decision's address is a child of the search, not a page of its
            own: the search stays mounted while the address changes, so its
            results, filters and order are still there when it changes back. */}
        <Route path="/" element={<HomePage />}>
          <Route path="decisoes/:source/:identifier" element={null} />
        </Route>
      </Routes>
    </div>
  );
}

export default App;
