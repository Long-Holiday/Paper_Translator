import { Paper, TranslationConfig } from '../types/paper';

const API_BASE = '/api';

export interface PaperUpdates {
  papers: Paper[];
  removed_ids: number[];
}

export function pollTranslationUpdates(
  ids: number[],
  onUpdate: (updates: PaperUpdates) => void
): () => void {
  const params = new URLSearchParams();
  ids.forEach((id) => params.append('ids', String(id)));
  const controller = new AbortController();
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const poll = async () => {
    if (stopped) return;
    try {
      const response = await fetch(`${API_BASE}/papers/updates?${params}`, {
        signal: controller.signal,
        cache: 'no-store',
      });
      if (!response.ok) throw new Error('获取翻译进度失败');
      const updates: PaperUpdates = await response.json();
      if (stopped) return;
      onUpdate(updates);
      if (!updates.papers.some((paper) =>
        paper.translation_status === 'queued' || paper.translation_status === 'translating'
      )) {
        stopped = true;
      }
    } catch (error) {
      if (!stopped) console.warn('获取翻译进度失败，将自动重试:', error);
    }
    // 上一次请求完成后再计时，慢请求不会堆积。
    if (!stopped) timer = setTimeout(poll, 1000);
  };

  void poll();
  return () => {
    stopped = true;
    if (timer !== undefined) clearTimeout(timer);
    controller.abort();
  };
}

export async function getPapers(search?: string): Promise<Paper[]> {
  const url = new URL(`${window.location.origin}${API_BASE}/papers`);
  if (search && search.trim()) {
    url.searchParams.set('search', search.trim());
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error('获取论文列表失败');
  return res.json();
}

export async function getPaper(id: number): Promise<Paper> {
  const res = await fetch(`${API_BASE}/papers/${id}`);
  if (!res.ok) throw new Error('获取论文详情失败');
  return res.json();
}

export async function uploadPaper(file: File): Promise<Paper> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/papers`, {
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
  const res = await fetch(`${API_BASE}/papers/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('删除论文失败');
}

export async function startTranslate(id: number): Promise<{ status: string; message?: string }> {
  const res = await fetch(`${API_BASE}/papers/${id}/translate`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '启动翻译失败' }));
    throw new Error(err.detail || '启动翻译失败');
  }
  return res.json();
}

export async function updateReadingPosition(id: number, page: number): Promise<Paper> {
  const res = await fetch(`${API_BASE}/papers/${id}/reading-position`, {
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
  return `${API_BASE}/papers/${id}/original`;
}

export function getTranslatedPdfUrl(id: number): string {
  return `${API_BASE}/papers/${id}/translated`;
}

export async function getTranslationConfig(): Promise<TranslationConfig> {
  const res = await fetch(`${API_BASE}/translation/config`);
  if (!res.ok) throw new Error('获取翻译设置失败');
  return res.json();
}

export async function updateTranslationConfig(cfg: Partial<TranslationConfig>): Promise<void> {
  const res = await fetch(`${API_BASE}/translation/config`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(cfg),
  });
  if (!res.ok) throw new Error('更新翻译设置失败');
}
