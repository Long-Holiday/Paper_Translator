import { Paper, TranslationConfig } from '../types/paper';
import { authFetch, getToken } from './auth';

const API_BASE = '/api';

export interface PaperUpdates {
  papers: Paper[];
  removed_ids: number[];
}

export function subscribeTranslationUpdates(
  ids: number[],
  onUpdate: (updates: PaperUpdates) => void
): () => void {
  const params = new URLSearchParams();
  ids.forEach((id) => params.append('ids', String(id)));
  const token = getToken();
  if (token) {
    params.append('token', token);
  }
  const source = new EventSource(`${API_BASE}/papers/events?${params}`);
  source.addEventListener('papers', (event) => {
    onUpdate(JSON.parse((event as MessageEvent).data));
  });
  source.addEventListener('done', () => source.close());
  // 连接中断时由 EventSource 自动重连；页面退出时显式关闭。
  return () => source.close();
}

export async function getPapers(search?: string): Promise<Paper[]> {
  const url = new URL(`${window.location.origin}${API_BASE}/papers`);
  if (search && search.trim()) {
    url.searchParams.set('search', search.trim());
  }
  const res = await authFetch(url.toString());
  if (!res.ok) throw new Error('获取论文列表失败');
  return res.json();
}

export async function getPaper(id: number): Promise<Paper> {
  const res = await authFetch(`${API_BASE}/papers/${id}`);
  if (!res.ok) throw new Error('获取论文详情失败');
  return res.json();
}

export async function uploadPaper(file: File): Promise<Paper> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await authFetch(`${API_BASE}/papers`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '上传失败' }));
    throw new Error(err.detail || '上传论文失败');
  }
  return res.json();
}

export async function deletePaper(id: number): Promise<void> {
  const res = await authFetch(`${API_BASE}/papers/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '删除论文失败' }));
    throw new Error(err.detail || '删除论文失败');
  }
}

export async function startTranslate(id: number): Promise<{ status: string; message?: string }> {
  const res = await authFetch(`${API_BASE}/papers/${id}/translate`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '启动翻译失败' }));
    throw new Error(err.detail || '启动翻译失败');
  }
  return res.json();
}

export async function updateReadingPosition(id: number, page: number): Promise<Paper> {
  const res = await authFetch(`${API_BASE}/papers/${id}/reading-position`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ page }),
  });
  if (!res.ok) throw new Error('更新阅读进度失败');
  return res.json();
}

export function getOriginalPdfUrl(id: number): string {
  const token = getToken();
  return token
    ? `${API_BASE}/papers/${id}/original?token=${encodeURIComponent(token)}`
    : `${API_BASE}/papers/${id}/original`;
}

export function getTranslatedPdfUrl(id: number): string {
  const token = getToken();
  return token
    ? `${API_BASE}/papers/${id}/translated?token=${encodeURIComponent(token)}`
    : `${API_BASE}/papers/${id}/translated`;
}

export async function getTranslationConfig(): Promise<TranslationConfig> {
  const res = await authFetch(`${API_BASE}/translation/config`);
  if (!res.ok) throw new Error('获取翻译设置失败');
  return res.json();
}

export async function updateTranslationConfig(cfg: Partial<TranslationConfig>): Promise<void> {
  const res = await authFetch(`${API_BASE}/translation/config`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(cfg),
  });
  if (!res.ok) throw new Error('更新翻译设置失败');
}
