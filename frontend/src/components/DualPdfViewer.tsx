import React, { useLayoutEffect, useMemo } from 'react';
import { PdfViewer } from './PdfViewer';
import { Paper } from '../types/paper';
import { getOriginalPdfUrl, getTranslatedPdfUrl } from '../api/papers';
import { Languages, Loader2 } from 'lucide-react';
import { createScrollSync } from './scrollSync';

interface Props {
  paper: Paper;
  currentPage: number;
  scale: number;
  syncEnabled: boolean;
  onTotalPages: (total: number) => void;
  onPageChange: (page: number) => void;
  onStartTranslate: () => void;
}

export const DualPdfViewer: React.FC<Props> = ({
  paper,
  currentPage,
  scale,
  syncEnabled,
  onTotalPages,
  onPageChange,
  onStartTranslate,
}) => {
  const originalUrl = getOriginalPdfUrl(paper.id);
  const translatedUrl = getTranslatedPdfUrl(paper.id);
  const isTranslated = paper.translation_status === 'completed';
  const isTranslating = paper.translation_status === 'translating' || paper.translation_status === 'queued';
  const scrollSync = useMemo(
    () => createScrollSync(currentPage, scale),
    [paper.id, syncEnabled],
  );

  useLayoutEffect(() => {
    scrollSync.setView(currentPage, scale);
  }, [scrollSync, currentPage, scale]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 auto-rows-fr gap-4 h-full min-h-0 w-full">
      {/* 左侧：英文原文 */}
      <div className="flex flex-col h-full min-h-0 min-w-0 bg-slate-100/80 rounded-2xl border border-slate-200 overflow-hidden shadow-inner">
        <div className="shrink-0 px-4 py-2.5 bg-slate-200/60 border-b border-slate-200 flex items-center justify-between text-xs font-semibold text-slate-700">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-sky-500"></span>
            英文原文 (Original)
          </span>
          <span className="text-slate-500">Page {currentPage}</span>
        </div>
        <PdfViewer
          url={originalUrl}
          page={currentPage}
          scale={scale}
          title="英文原文"
          onTotalPages={onTotalPages}
          onPageChange={onPageChange}
          onScroll={syncEnabled ? (container) => scrollSync.scroll('original', container) : undefined}
          onViewportReady={syncEnabled ? (container) => scrollSync.ready('original', container) : undefined}
          className="flex-1"
        />
      </div>

      {/* 右侧：中文翻译 */}
      <div className="flex flex-col h-full min-h-0 min-w-0 bg-slate-100/80 rounded-2xl border border-slate-200 overflow-hidden shadow-inner">
        <div className="shrink-0 px-4 py-2.5 bg-slate-200/60 border-b border-slate-200 flex items-center justify-between text-xs font-semibold text-slate-700">
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${isTranslated ? 'bg-emerald-500' : 'bg-amber-400'}`}></span>
            中文译文 (Translation)
          </span>
          {isTranslated && <span className="text-slate-500">第 {currentPage} 页</span>}
        </div>

        {isTranslated ? (
          <PdfViewer
            url={translatedUrl}
            page={currentPage}
            scale={scale}
            title="中文译文"
            onPageChange={onPageChange}
            onScroll={syncEnabled ? (container) => scrollSync.scroll('translated', container) : undefined}
            onViewportReady={syncEnabled ? (container) => scrollSync.ready('translated', container) : undefined}
            className="flex-1"
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-50/50">
            {isTranslating ? (
              <div className="flex flex-col items-center">
                <Loader2 className="w-10 h-10 text-sky-600 animate-spin mb-3" />
                <h4 className="text-base font-bold text-slate-800 mb-1">
                  正在生成中文翻译版本 ({paper.translation_progress}%)
                </h4>
                <p className="text-xs text-slate-500 max-w-sm mb-4">
                  后台正在进行数学公式与版面智能排版，完成后右侧将自动加载呈现。
                </p>
                <div className="w-48 bg-slate-200 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-sky-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(paper.translation_progress, 15)}%` }}
                  />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mb-3">
                  <Languages className="w-6 h-6" />
                </div>
                <h4 className="text-base font-bold text-slate-800 mb-1">
                  {paper.translation_status === 'failed' ? '翻译未成功' : '尚未进行中文翻译'}
                </h4>
                <p className="text-xs text-slate-500 max-w-sm mb-5">
                  {paper.translation_error
                    ? `失败原因: ${paper.translation_error}`
                    : '该论文目前仅有原始英文版本，点击下方按钮立即启动双语翻译引擎。'}
                </p>
                <button
                  onClick={onStartTranslate}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold rounded-xl shadow-md shadow-sky-600/20 transition-all hover:scale-105 active:scale-95"
                >
                  <Languages className="w-4 h-4" />
                  <span>{paper.translation_status === 'failed' ? '重试翻译' : '立即启动翻译'}</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
