import { useState } from 'react';
import { MagnifyingGlass, SlidersHorizontal } from '@phosphor-icons/react';

function HomePage() {
  const [value, setValue] = useState('prescrição intercorrente em execução fiscal');
  const [mode, setMode] = useState<'free' | 'exact'>('free');

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
  };

  return (
    <main className="search-page">
      <form className="legal-search" onSubmit={handleSubmit}>
        <div className="legal-search__field">
          <MagnifyingGlass size={20} aria-hidden="true" />

          <label className="sr-only" htmlFor="legal-search-input">
            Pesquisar decisões
          </label>

          <input
            id="legal-search-input"
            type="search"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Pesquise um assunto, fundamento ou frase exata"
            autoComplete="off"
          />
        </div>

        <div className="legal-search__actions">
          <div className="search-mode" role="group" aria-label="Modalidade da pesquisa">
            <span
              className="search-mode__indicator"
              style={{
                transform: mode === 'free' ? 'translateX(0%)' : 'translateX(100%)',
              }}
            />

            <button
              type="button"
              className={mode === 'free' ? 'is-active' : ''}
              aria-pressed={mode === 'free'}
              onClick={() => setMode('free')}
            >
              Termo livre
            </button>

            <button
              type="button"
              className={mode === 'exact' ? 'is-active' : ''}
              aria-pressed={mode === 'exact'}
              onClick={() => setMode('exact')}
            >
              Frase exata
            </button>
          </div>

          <button type="button" className="filter-button" aria-label="Abrir filtros">
            <SlidersHorizontal size={17} aria-hidden="true" />
            <span>Filtros</span>
            <span className="filter-button__count">4</span>
          </button>

          <button type="submit" className="search-button">
            Pesquisar
          </button>
        </div>
      </form>
    </main>
  );
}

export default HomePage;
