import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowUp, ArrowUpRight, BookOpen, Check, ChevronRight, CircleHelp, Download, FileText, Layers, LoaderCircle, LogOut, MessageSquare, Plus, Search, ShieldCheck, Sparkles, Trash2, Upload, X } from 'lucide-react';
import { api, Answer, Conversation, Document, Source, Turn, User } from './api';
import './style.css';

function Brand() { return <a className="brand" href="/" aria-label="CiteWise home"><span className="brand-icon"><BookOpen size={23}/></span>CiteWise<span className="brand-dot">.</span></a>; }
function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState('excerpt');
  useEffect(() => {
    api<User>('/auth/me').then(setUser).catch(() => {}).finally(() => setLoading(false));
    api<{mode: string}>('/health').then(s => setMode(s.mode)).catch(() => {});
  }, []);
  if (loading) return <div className="loading-screen"><Brand/><LoaderCircle className="spin"/></div>;
  return user ? <Workspace user={user} mode={mode} onLogout={() => setUser(null)}/> : <Auth onLogin={setUser}/>;
}

function Auth({ onLogin }: { onLogin: (u: User) => void }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); setError(''); setBusy(true);
    const fields = new FormData(e.currentTarget);
    try { onLogin(await api<User>('/auth/' + (register ? 'register' : 'login'), { method: 'POST', body: JSON.stringify(Object.fromEntries(fields)) })); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <div className="auth-page"><section className="auth-story"><Brand/><div className="story-content"><span className="eyebrow">LESS SEARCHING. MORE UNDERSTANDING.</span><h1>Your documents.<br/>A clearer picture.</h1><p>Turn a stack of PDFs into a conversation.<br/>Find the answer. Follow the evidence.</p><div className="paper-stack"><div className="paper back"/><div className="paper front"><FileText size={30}/><span>KNOWLEDGE, CONNECTED</span><div className="paper-line long"/><div className="paper-line"/><div className="highlight-line"/><div className="paper-line long"/><div className="paper-note"><ShieldCheck size={17}/> Every insight starts with a source.</div></div></div></div><small>Built for curious minds.</small></section><section className="auth-panel"><div className="auth-form"><span className="mini-icon"><Sparkles size={23}/></span><h2>{register ? 'Make room for discovery.' : 'Welcome back.'}</h2><p>{register ? 'Create your own document workspace.' : 'Your next insight is waiting in your documents.'}</p><form onSubmit={submit}><label>Username<input name="username" autoComplete="username" required minLength={3} maxLength={40} pattern="[a-zA-Z0-9_.\-]+" placeholder="Your username"/></label><label>Password<input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} required minLength={10} maxLength={128} placeholder="At least 10 characters"/></label>{error && <div role="alert" className="error">{error}</div>}<button className="primary full" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18}/> : register ? 'Create workspace' : 'Sign in'}<ArrowUpRight size={18}/></button></form><p className="auth-switch">{register ? 'Already have an account?' : 'New to CiteWise?'} <button onClick={() => { setRegister(!register); setError(''); }}>{register ? 'Sign in' : 'Create an account'}</button></p><div className="privacy"><ShieldCheck size={17}/> Your documents stay in this installation. Local AI runs through Ollama.</div></div></section></div>;
}

function Workspace({ user, mode, onLogout }: { user: User; mode: string; onLogout: () => void }) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [history, setHistory] = useState<Conversation[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [convo, setConvo] = useState<string>();
  const [question, setQuestion] = useState('');
  const [search, setSearch] = useState('');
  const [compare, setCompare] = useState(false);
  const [asking, setAsking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [help, setHelp] = useState(false);
  const [drag, setDrag] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const busy = asking || uploading;
  useEffect(() => {
    if (!activeSource && !help) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const focusable = () => Array.from(dialog?.querySelectorAll<HTMLElement>('button, a[href], iframe, input, [tabindex="0"]') || []);
    focusable()[0]?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setActiveSource(null); setHelp(false); }
      if (event.key === 'Tab') {
        const items = focusable(); const first = items[0]; const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus(); };
  }, [activeSource, help]);
  async function refresh() { const [d, h] = await Promise.all([api<Document[]>('/documents'), api<Conversation[]>('/conversations')]); setDocs(d); setHistory(h); }
  useEffect(() => { refresh().catch(e => setError(e.message)); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [turns, asking]);
  async function upload(files: FileList | File[]) {
    setUploading(true); setError(''); setNotice('');
    let count = 0; const warnings: string[] = [];
    for (const file of Array.from(files)) {
      if (file.size > 20 * 1024 * 1024) { warnings.push(`${file.name}: exceeds 20 MB.`); continue; }
      const form = new FormData(); form.append('file', file);
      try { const result = await api<{document: Document; warning: string | null}>('/documents', { method: 'POST', body: form }); count++; if (result.warning) warnings.push(result.warning); }
      catch (e) { warnings.push(`${file.name}: ${(e as Error).message}`); }
    }
    try { await refresh(); } catch (e) { setError((e as Error).message); }
    setNotice(count ? `${count} document${count > 1 ? 's' : ''} added. Your sources are ready.` : '');
    if (warnings.length) setError(warnings.join(' '));
    setUploading(false); if (fileInput.current) fileInput.current.value = '';
  }
  async function ask(e: React.FormEvent) {
    e.preventDefault(); if (!question.trim() || busy) return;
    if (compare && (selected.length < 2 || selected.length > 3)) { setError('Select two or three documents to compare.'); return; }
    setAsking(true); setError('');
    try {
      const turn = await api<Turn>('/ask', { method: 'POST', body: JSON.stringify({ question, document_ids: selected, conversation_id: convo, compare }) });
      setTurns(prev => [...prev, turn]); setConvo(turn.conversation_id); setQuestion(''); await refresh();
    } catch (e) { setError((e as Error).message); } finally { setAsking(false); }
  }
  async function remove(doc: Document) {
    if (!window.confirm(`Delete “${doc.name}”? Saved answers citing this document will also be removed.`)) return;
    try { await api(`/documents/${doc.id}`, { method: 'DELETE' }); setSelected(s => s.filter(id => id !== doc.id)); setActiveSource(null); setTurns([]); setConvo(undefined); await refresh(); }
    catch (e) { setError((e as Error).message); }
  }
  async function loadConversation(id: string) {
    try { setTurns(await api<Turn[]>(`/conversations/${id}`)); setConvo(id); setActiveSource(null); }
    catch (e) { setError((e as Error).message); }
  }
  function newConversation() { setConvo(undefined); setTurns([]); setActiveSource(null); setQuestion(''); setError(''); }
  function exportChat() {
    const text = turns.map(t => `## ${t.question}\n\n${t.result.message}\n\n${t.result.paragraphs.map(p => p.text + ' ' + p.source_ids.map(i => `[${i}]`).join(' ')).join('\n\n')}\n\nSources:\n${t.result.sources.map(s => `[${s.id}] ${s.document_name}, PDF page ${s.page}`).join('\n')}`).join('\n\n---\n\n');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' })); const link = document.createElement('a'); link.href = url; link.download = 'citewise-conversation.md'; link.click(); URL.revokeObjectURL(url);
  }
  return <div className="workspace"><aside className="sidebar"><Brand/><div className="workspace-label"><span className="avatar small">{user.username.slice(0, 1).toUpperCase()}</span><span>Personal workspace<small>Your private knowledge space</small></span></div><button className="new-chat" onClick={newConversation} disabled={busy}><Plus size={18}/> New conversation<span>↗</span></button><div className="nav-label">WORKSPACE</div><div className="nav-item active"><BookOpen size={18}/> Ask your documents<span>{docs.length}</span></div><div className="sidebar-history"><div className="nav-label">RECENT CONVERSATIONS</div>{history.length ? history.map(h => <div className={'history-row ' + (convo === h.id ? 'chosen' : '')} key={h.id}><button disabled={busy} onClick={() => loadConversation(h.id)}><MessageSquare size={15}/><span>{h.title}</span></button><button className="history-delete" aria-label={'Delete conversation ' + h.title} disabled={busy} onClick={async () => { if (!confirm('Delete this conversation?')) return; try { await api(`/conversations/${h.id}`, { method: 'DELETE' }); if (convo === h.id) newConversation(); await refresh(); } catch (e) { setError((e as Error).message); } }}><X size={13}/></button></div>) : <p className="empty-history">Your conversations will<br/>find a home here.</p>}</div><button className="help-link" onClick={() => setHelp(true)}><CircleHelp size={17}/> A little help getting started</button><div className="profile"><span className="avatar">{user.username.slice(0, 1).toUpperCase()}</span><div>{user.username}<small>Personal account</small></div><button aria-label="Sign out" disabled={busy} onClick={async () => { try { await api('/auth/logout', { method: 'POST' }); onLogout(); } catch (e) { setError((e as Error).message); } }}><LogOut size={17}/></button></div></aside>
  <main className="main"><header className="topbar"><span>Workspace <ChevronRight size={14}/> <strong>Ask your documents</strong></span><span className="mode-pill"><i/>{mode === 'ollama' ? 'Local AI enabled' : 'Source excerpt mode'}</span></header><div className="page-heading"><div><span className="eyebrow">YOUR KNOWLEDGE, WITH CONTEXT</span><h1>Ask. Discover. Understand.</h1><p>A conversation with your documents. An answer you can trace.</p></div><button className="outline" onClick={() => fileInput.current?.click()} disabled={busy}><Plus size={17}/> Add documents</button></div>
  <div className="work-grid"><section className="documents-panel"><div className="panel-title"><h2>Your sources <span>{docs.length}</span></h2><Layers size={18}/></div><p className="panel-description">Choose sources to focus your answer.<br/>None selected searches all documents.</p><label className="search-field"><Search size={16}/><input aria-label="Find a document" placeholder="Find a document..." value={search} onChange={e => setSearch(e.target.value)}/></label><div className={'dropzone ' + (drag ? 'dragging' : '')} onDragOver={e => { e.preventDefault(); if (!busy) setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); if (!busy) upload(e.dataTransfer.files); }}><button onClick={() => fileInput.current?.click()} disabled={busy}>{uploading ? <LoaderCircle size={23} className="spin"/> : <Upload size={23}/>}<strong>{uploading ? 'Reading your documents…' : 'Drop your PDFs here'}</strong><span>or <em>browse files</em></span><small>Up to 20 MB · 200 pages per PDF</small></button><input ref={fileInput} type="file" accept="application/pdf,.pdf" multiple hidden onChange={e => { if (e.target.files) upload(e.target.files); }}/></div>
  <div className="document-list">{docs.filter(d => d.name.toLowerCase().includes(search.toLowerCase())).map(d => <div className={'document ' + (selected.includes(d.id) ? 'selected' : '')} key={d.id}><label><input type="checkbox" checked={selected.includes(d.id)} disabled={busy} onChange={() => setSelected(s => s.includes(d.id) ? s.filter(i => i !== d.id) : [...s, d.id])}/><span className="pdf-icon"><FileText size={19}/><small>PDF</small></span><span className="document-text"><strong title={d.name}>{d.name}</strong><small>{d.page_count} pages · {(d.size / 1024).toFixed(0)} KB</small></span></label><div className="doc-footer"><span><i/>{d.indexed_model ? 'Semantic search ready' : 'Keyword search ready'}</span><button aria-label={'Delete ' + d.name} disabled={busy} onClick={() => remove(d)}><Trash2 size={13}/></button></div>{mode === 'ollama' && !d.indexed_model && <button className="reindex" disabled={busy} onClick={async () => { setUploading(true); try { await api(`/documents/${d.id}/reindex`, { method: 'POST' }); await refresh(); } catch (e) { setError((e as Error).message); } finally { setUploading(false); } }}>Reindex for semantic search</button>}</div>)}{docs.length === 0 && <div className="empty-sources"><FileText size={26}/><p>A fresh page.</p><span>Add your first PDF to get started.</span></div>}{docs.length > 0 && !docs.some(d => d.name.toLowerCase().includes(search.toLowerCase())) && <p className="empty-history">No documents match your search.</p>}</div><div className="source-footer"><ShieldCheck size={16}/><span>Only your documents. Always your sources.</span></div></section>
  <section className="chat-panel"><div className="chat-toolbar"><span><span className="status-dot"/>Document conversation</span><div>{turns.length > 0 && <button aria-label="Export conversation" title="Export conversation" onClick={exportChat}><Download size={17}/></button>}<button className={'compare-toggle ' + (compare ? 'enabled' : '')} disabled={busy} aria-pressed={compare} onClick={() => setCompare(!compare)}><Layers size={15}/> Compare</button></div></div><div className="chat-content" aria-live="polite">{turns.length === 0 && !asking ? <div className="chat-welcome"><div className="welcome-icon"><Sparkles size={30}/></div><span className="eyebrow">START WITH A QUESTION</span><h2>There's more in your documents.<br/>Let's find it.</h2><p>Bring your notes, research, or reports.<br/>Ask a question and explore the sources behind it.</p><div className="suggestions">{['What are the main findings?', 'Explain the key concepts in simple terms.', 'Compare the approaches in these documents.'].map((q, i) => <button key={q} onClick={() => { setQuestion(q); if (i === 2) setCompare(true); questionInput.current?.focus(); }}><span>{i === 0 ? <Search size={17}/> : i === 1 ? <BookOpen size={17}/> : <Layers size={17}/>}</span>{q}<ArrowUpRight size={16}/></button>)}</div><div className="welcome-footnote"><Check size={14}/> Page-level citations <span>·</span> <Check size={14}/> Your sources, in view</div></div> : turns.map(t => <div className="turn" key={t.id}><div className="question-bubble"><span className="eyebrow">YOU ASKED</span><p>{t.question}</p></div><AnswerView answer={t.result} onSource={setActiveSource}/></div>)}{asking && <div className="thinking"><LoaderCircle size={18} className="spin"/> Finding evidence in your documents…</div>}<div ref={bottom}/></div>
  <div className="composer-area">{notice && <div className="notice" role="status">{notice}<button aria-label="Dismiss notice" onClick={() => setNotice('')}><X size={14}/></button></div>}{error && <div className="error" role="alert">{error}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={14}/></button></div>}{compare && <div className="compare-info">Compare mode · Select 2–3 sources. Each question is answered independently.</div>}<form className="composer" onSubmit={ask}><textarea ref={questionInput} aria-label="Ask a question" placeholder={docs.length ? 'Ask anything about your documents…' : 'Add a PDF to start a conversation…'} value={question} maxLength={2000} disabled={!docs.length || busy} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }}/><div className="composer-bottom"><span><FileText size={13}/>{selected.length ? `${selected.length} sources selected` : `All ${docs.length} sources`}<span className="key-hint">Shift + Enter for a new line</span></span><button className="send" aria-label="Send question" disabled={!docs.length || question.trim().length < 3 || busy}>{asking ? <LoaderCircle size={19} className="spin"/> : <ArrowUp size={19}/>}</button></div></form><p className="composer-note">{mode === 'excerpt' ? 'Excerpt mode finds matching passages. Enable Ollama for AI-written answers.' : 'AI can make mistakes. Follow the citations to verify an answer.'}</p></div></section></div><footer className="page-footer"><span>CITEWISE</span> A little less searching. A lot more clarity.</footer></main>
  {activeSource && <div className="modal-backdrop" onClick={() => setActiveSource(null)}><section className="source-modal" role="dialog" aria-modal="true" aria-label="Source preview" onClick={e => e.stopPropagation()}><div className="modal-header"><div><span className="eyebrow">FOLLOW THE EVIDENCE</span><h2>{activeSource.document_name}</h2><p>PDF page {activeSource.page}</p></div><button aria-label="Close source preview" onClick={() => setActiveSource(null)}><X/></button></div><blockquote>{activeSource.text}</blockquote><a className="source-link" href={`/api/documents/${activeSource.document_id}/file#page=${activeSource.page}`} target="_blank" rel="noreferrer">Open PDF at page {activeSource.page}<ArrowUpRight size={16}/></a><iframe title="PDF source page" src={`/api/documents/${activeSource.document_id}/file#page=${activeSource.page}`}/></section></div>}
  {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><section className="help-modal" role="dialog" aria-modal="true" aria-label="Getting started" onClick={e => e.stopPropagation()}><button className="close" aria-label="Close help" onClick={() => setHelp(false)}><X/></button><span className="mini-icon"><BookOpen/></span><h2>From PDF to perspective.</h2><ol><li><strong>Add a document.</strong> Upload a PDF with selectable text. Scanned pages need OCR first.</li><li><strong>Choose your focus.</strong> Select documents, or leave everything unchecked to search them all.</li><li><strong>Ask a specific question.</strong> Use subject terms found in your document for better excerpt results. Questions are independent; repeat the subject in follow-ups.</li><li><strong>Follow the citation.</strong> Open a source card to see the excerpt and original PDF page.</li></ol><p>Compare mode needs two or three selected documents. In excerpt mode it shows relevant passages side by side in the answer; Ollama mode writes a comparison.</p><button className="primary" onClick={() => setHelp(false)}>Got it<Check size={16}/></button></section></div>}
  </div>;
}

function AnswerView({ answer, onSource }: { answer: Answer; onSource: (s: Source) => void }) {
  return <div className="answer"><div className="answer-heading"><span className="answer-logo"><Sparkles size={15}/></span><strong>CiteWise</strong><span>{answer.mode === 'ai' ? 'AI answer' : 'Source excerpts'}</span><small>{(answer.elapsed_ms / 1000).toFixed(1)}s</small></div><p className={'answer-message ' + (answer.insufficient_evidence ? 'no-evidence' : '')}>{answer.message}</p>{answer.warning && <div className="warning">{answer.warning}</div>}{answer.paragraphs.map((p, i) => <p className="answer-paragraph" key={i}>{p.text} {p.source_ids.map(id => <button className="citation" key={id} onClick={() => { const s = answer.sources.find(s => s.id === id); if (s) onSource(s); }} aria-label={`View source ${id}`}>{id}</button>)}</p>)}{answer.sources.length > 0 && <div className="answer-sources"><span className="eyebrow">{answer.insufficient_evidence ? 'RELATED PASSAGES' : 'EXPLORE THE SOURCES'}</span><div>{answer.sources.map(s => <button className="source-card" key={s.id} onClick={() => onSource(s)}><FileText size={16}/><span><strong>{s.document_name}</strong><small>Page {s.page} · Source {s.id}</small></span><ArrowUpRight size={14}/></button>)}</div></div>}</div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
