export type TranslationStatus = 'pending' | 'queued' | 'translating' | 'completed' | 'failed';

export interface Paper {
  id: number;
  title: string;
  original_filename: string;
  page_count: number | null;
  translation_status: TranslationStatus;
  translation_progress: number;
  translation_error: string | null;
  last_read_page: number;
  created_at: string;
  updated_at: string;
}

export interface TranslationConfig {
  source_language: string;
  target_language: string;
  service: string;
  model: string;
  api_key?: string;
  api_key_masked?: string;
  base_url?: string;
  thread: number;
  preserve_layout: boolean;
}
