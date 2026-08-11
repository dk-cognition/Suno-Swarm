import React, { useEffect, useState } from 'react';
import { api } from './api';

const GENRES = ['dream-pop', 'shoegaze', 'lo-fi-hiphop', 'synthwave', 'drum-and-bass'];

export default function Studio() {
  const [prompt, setPrompt] = useState({
    text: '',
    genre: GENRES[0],
    bpm: 100,
    duration_seconds: 60,
    reference_audio_url: '',
  });
  const [job, setJob] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  useEffect(() => {
    api.tracks().then(setTracks).catch(() => setTracks([]));
  }, [job?.status]);

  useEffect(() => {
    if (!job || ['complete', 'failed'].includes(job.status)) return undefined;
    const timer = setInterval(() => {
      api.job(job.id || job.job_id).then(setJob).catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, [job]);

  async function submit(event) {
    event.preventDefault();
    const created = await api.submitPrompt(prompt);
    setJob({ id: created.job_id, status: created.status });
  }

  async function search(event) {
    event.preventDefault();
    setResults(await api.search(query));
  }

  return (
    <div className="studio">
      <h1>Studio</h1>

      <form className="composer" onSubmit={submit}>
        <textarea
          value={prompt.text}
          placeholder="dream pop with shoegaze guitars, female vocals"
          onChange={(e) => setPrompt({ ...prompt, text: e.target.value })}
        />
        <div className="controls">
          <select
            value={prompt.genre}
            onChange={(e) => setPrompt({ ...prompt, genre: e.target.value })}
          >
            {GENRES.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <input
            type="number"
            min="40"
            max="220"
            value={prompt.bpm}
            onChange={(e) => setPrompt({ ...prompt, bpm: Number(e.target.value) })}
          />
          <input
            type="number"
            min="15"
            max="300"
            value={prompt.duration_seconds}
            onChange={(e) => setPrompt({ ...prompt, duration_seconds: Number(e.target.value) })}
          />
          <input
            type="url"
            placeholder="reference clip url (optional)"
            value={prompt.reference_audio_url}
            onChange={(e) => setPrompt({ ...prompt, reference_audio_url: e.target.value })}
          />
          <button type="submit">Render</button>
        </div>
      </form>

      {job && (
        <p className="job">
          job <code>{job.id}</code> — {job.status}
        </p>
      )}

      <form className="search" onSubmit={search}>
        <input
          value={query}
          placeholder="search your library"
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit">Search</button>
      </form>

      {results.length > 0 && (
        <ul className="results">
          {results.map((r) => (
            <li key={r.id} dangerouslySetInnerHTML={{ __html: `<strong>${r.title}</strong> — ${r.prompt_text || ''}` }} />
          ))}
        </ul>
      )}

      <h2>Library</h2>
      <ul className="library">
        {tracks.map((t) => (
          <li key={t.id}>
            <span className="title">{t.title}</span>
            <audio controls src={api.downloadUrl(t.id)} />
          </li>
        ))}
      </ul>
    </div>
  );
}
