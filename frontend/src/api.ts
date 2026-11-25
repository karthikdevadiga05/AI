export type User = { id: string; username: string };
export type Document = { id: string; name: string; page_count: number; chunk_count: number; size: number; indexed_model: string | null; created_at: number };
export type Source = { id: number; document_id: string; document_name: string; page: number; text: string; score: number };
export type Answer = { paragraphs: { text: string; source_ids: number[] }[]; sources: Source[]; mode: string; insufficient_evidence: boolean; warning: string | null; message: string; elapsed_ms: number; compare: boolean };
export type Turn = { id: string; question: string; result: Answer; conversation_id?: string };
export type Conversation = { id: string; title: string; created_at: number };

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch('/api' + url, { credentials: 'same-origin', ...options,
    headers: options.body instanceof FormData ? options.headers : { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!response.ok) {
    let message = 'Something went wrong. Please try again.';
    try { const data = await response.json(); message = typeof data.detail === 'string' ? data.detail : 'Please check your input and try again.'; } catch { /* plain error response */ }
    throw new Error(message);
  }
  return response.status === 204 ? undefined as T : response.json();
}
