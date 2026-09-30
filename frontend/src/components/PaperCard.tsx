import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Paper } from '../types/paper';
import { TranslationStatus } from './TranslationStatus';
import { BookOpen, Languages, Trash2, FileText, Bookmark, AlertCircle, RefreshCw, Loader2 } from 'lucide-react';

interface Props {
  paper: Paper;
  onTranslate: (id: number) => void;
  onDelete: (id: number) => void;
}

export const PaperCard: React.FC<Props> = ({ paper, onTranslate, onDelete }) => {
  const navigate = useNavigate();
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm(`确定要彻底删除论文《${paper.title}》吗？\n（将同时清理本地原始 PDF 与翻译后文件）`)) {
      setIsDeleting(true);
      onDelete(paper.id);
    }
  };

  const handleTranslateClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onTranslate(paper.id);
  };

  const handleOpenReader = () => {
    navigate(`/paper/${paper.id}`);
  };

  const isTranslating = paper.translation_status === 'translating' || paper.translation_status === 'queued';
  const isCompleted = paper.translation_status === 'completed';

  return (
    <div
      onClick={handleOpenReader}
      className="group bg-white rounded-2xl p-5 border border-slate-200/90 shadow-sm hover:shadow-md hover:border-sky-300 transition-all cursor-pointer flex flex-col justify-between relative"
    >
      <div>
        {/* 顶部：状态徽章与常显的删除按钮 */}
        <div className="flex items-center justify-between gap-3 mb-3">
          <TranslationStatus
            status={paper.translation_status}
            progress={paper.translation_progress}
            error={paper.translation_error}
          />

          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-transparent hover:border-rose-200"
            title="删除此论文及本地文件"
          >
            {isDeleting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-500" />
            ) : (
              <Trash2 className="w-3.5 h-3.5" />
            )}
            <span className="text-[11px]">删除</span>
          </button>
        </div>

        {/* 论文标题 */}
        <h3 className="text-base font-bold text-slate-900 line-clamp-2 group-hover:text-sky-600 transition-colors mb-2">
          {paper.title}
        </h3>

        {/* 文件名与页数信息 */}
        <div className="flex items-center gap-2 text-xs text-slate-500 mb-3">
          <span className="flex items-center gap-1 truncate max-w-[200px]" title={paper.original_filename}>
            <FileText className="w-3.5 h-3.5 shrink-0 text-slate-400" />
            {paper.original_filename}
          </span>
          <span>•</span>
          <span>{paper.page_count ? `${paper.page_count} 页` : '未知页数'}</span>
        </div>

        {/* 上次阅读进度 */}
        {paper.last_read_page > 1 && (
          <div className="mb-3 flex items-center gap-1.5 text-xs text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-lg w-fit">
            <Bookmark className="w-3.5 h-3.5" />
            <span>上次读至第 {paper.last_read_page} 页</span>
          </div>
        )}

        {/* 翻译中进度条 */}
        {isTranslating && (
          <div className="w-full bg-slate-100 rounded-full h-1.5 mb-3 overflow-hidden">
            <div
              className="bg-sky-500 h-1.5 rounded-full transition-all duration-300 animate-pulse"
              style={{ width: `${Math.max(paper.translation_progress, 15)}%` }}
            />
          </div>
        )}

        {/* 失败错误提示 */}
        {paper.translation_error && (
          <div className="mb-3 p-2.5 bg-rose-50 border border-rose-100 rounded-lg text-xs text-rose-600 flex items-start gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span className="line-clamp-2">{paper.translation_error}</span>
          </div>
        )}
      </div>

      {/* 底部按钮栏 */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2 mt-auto">
        {!isCompleted && !isTranslating ? (
          <button
            onClick={handleTranslateClick}
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-sky-600 hover:text-sky-700 hover:bg-sky-50 rounded-lg transition-colors border border-sky-200"
          >
            {paper.translation_status === 'failed' ? (
              <>
                <RefreshCw className="w-3.5 h-3.5" />
                重新翻译
              </>
            ) : (
              <>
                <Languages className="w-3.5 h-3.5" />
                开始翻译
              </>
            )}
          </button>
        ) : (
          <div />
        )}

        <button
          onClick={(e) => {
            e.stopPropagation();
            handleOpenReader();
          }}
          className={`inline-flex items-center gap-1 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
            isCompleted
              ? 'bg-sky-600 text-white hover:bg-sky-700 shadow-sm'
              : 'text-slate-600 bg-slate-100 hover:bg-slate-200'
          }`}
        >
          <BookOpen className="w-3.5 h-3.5" />
          <span>{isCompleted ? '双栏阅读' : '查看原文'}</span>
        </button>
      </div>
    </div>
  );
};
