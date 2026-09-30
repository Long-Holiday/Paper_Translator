import React from 'react';
import { TranslationStatus as StatusType } from '../types/paper';
import { Loader2, CheckCircle2, AlertCircle, Clock, FileQuestion } from 'lucide-react';

interface Props {
  status: StatusType;
  progress: number;
  error?: string | null;
}

export const TranslationStatus: React.FC<Props> = ({ status, progress, error }) => {
  switch (status) {
    case 'completed':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          已完成
        </span>
      );
    case 'translating':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-sky-50 text-sky-700 border border-sky-200">
          <Loader2 className="w-3.5 h-3.5 text-sky-600 animate-spin" />
          翻译中 {progress > 0 ? `${progress}%` : ''}
        </span>
      );
    case 'queued':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
          <Clock className="w-3.5 h-3.5 text-amber-600" />
          排队中
        </span>
      );
    case 'failed':
      return (
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200 cursor-help"
          title={error || '翻译发生错误'}
        >
          <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
          翻译失败
        </span>
      );
    case 'pending':
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
          <FileQuestion className="w-3.5 h-3.5 text-slate-500" />
          未翻译
        </span>
      );
  }
};
