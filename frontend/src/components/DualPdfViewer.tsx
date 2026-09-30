import React, { useMemo } from 'react';
import { PdfViewer } from './PdfViewer';
import { Paper } from '../types/paper';
import { getOriginalPdfUrl, getTranslatedPdfUrl } from '../api/papers';
import { Languages, Loader2 } from 'lucide-react';
import { createScrollSync } from './scrollSync';

interface Props {
  paper: Paper;
  currentPage: number;
  navigationKey: number;
  scale: number;
  syncEnabled: boolean;
  onTotalPages: (total: number) => void;
  onPageChange: (page: number) => void;
  onStartTranslate: () => void;
}

export const DualPdfViewer: React.FC<Props> = ({
  paper,
  currentPage,
  navigationKey,
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

  const handleViewportReady = (side: 'original' | 'translated', container: HTMLDivElement) => {
    scrollSync.setView(currentPage, scale, navigationKey);
    scrollSync.ready(side, container);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 auto-rows-fr gap-0 h-full min-h-0 w-full">
      {/* 左侧：英文原文 */}
      <div className="flex flex-col h-full min-h-0 min-w-0 bg-white text-black overflow-hidden">
        <div className="shrink-0 h-8 px-3 bg-white flex items-center justify-between text-xs font-medium text-black">
          <span className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wide bg-sky-50">EN</span>
            英文原文
          </span>
          <span className="text-black opacity-50 text-[11px] tabular-nums">第 {currentPage} 页</span>
        </div>
        <PdfViewer
          url={originalUrl}
          page={currentPage}
          navigationKey={navigationKey}
          scale={scale}
          title="英文原文"
          onTotalPages={onTotalPages}
          onPageChange={onPageChange}
          onScroll={syncEnabled ? (container) => scrollSync.scroll('original', container) : undefined}
          onViewportReady={syncEnabled ? (container) => handleViewportReady('original', container) : undefined}
          className="flex-1"
        />
      </div>

      {/* 右侧：中文翻译 */}
      <div className="flex flex-col h-full min-h-0 min-w-0 bg-white text-black overflow-hidden">
        <div className="shrink-0 h-8 px-3 bg-white flex items-center justify-between text-xs font-medium text-black">
          <span className="flex items-center gap-2">
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold tracking-wide ${isTranslated ? 'bg-emerald-50' : 'bg-amber-50'}`}>中</span>
            中文译文
          </span>
          {isTranslated && <span className="text-black opacity-50 text-[11px] tabular-nums">第 {currentPage} 页</span>}
        </div>

        {isTranslated ? (
          <PdfViewer
            url={translatedUrl}
            page={currentPage}
            navigationKey={navigationKey}
            scale={scale}
            title="中文译文"
            onPageChange={onPageChange}
            onScroll={syncEnabled ? (container) => scrollSync.scroll('translated', container) : undefined}
            onViewportReady={syncEnabled ? (container) => handleViewportReady('translated', container) : undefined}
            className="flex-1"
          />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-white">
            {isTranslating ? (
              <div className="flex flex-col items-center">
                <Loader2 className="w-10 h-10 text-sky-600 animate-spin mb-3" />
                <h4 className="text-base font-bold text-black mb-1">
                  正在生成中文翻译版本 ({paper.translation_progress}%)
                </h4>
                <p className="text-xs leading-relaxed text-black opacity-60 max-w-sm mb-4">
                  后台正在进行数学公式与版面智能排版，完成后右侧将自动加载呈现。
                </p>
                <div className="w-48 bg-slate-200 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-sky-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(0, Math.min(100, paper.translation_progress))}%` }}
                  />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mb-3">
                  <Languages className="w-6 h-6" />
                </div>
                <h4 className="text-base font-bold text-black mb-1">
                  {paper.translation_status === 'failed' ? '翻译未成功' : '尚未进行中文翻译'}
                </h4>
                <p className="text-xs leading-relaxed text-black opacity-60 max-w-sm mb-5">
                  {paper.translation_error
                    ? `失败原因: ${paper.translation_error}`
                    : '该论文目前仅有原始英文版本，点击下方按钮立即启动双语翻译引擎。'}
                </p>
                <button
                  onClick={onStartTranslate}
                  className="inline-flex items-center gap-2 px-5 py-2.5 reader-control bg-white text-black border border-slate-200 text-sm font-medium rounded-xl"
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
