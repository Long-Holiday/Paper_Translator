import React, { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
// @ts-ignore Vite resolves the PDF worker as a local build asset.
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { Loader2, AlertCircle } from 'lucide-react';
import { attachWheelPageNavigation } from './wheelPageNavigation';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface Props {
  url: string;
  page: number;
  scale: number;
  title: string;
  onTotalPages?: (total: number) => void;
  onPageChange?: (page: number) => void;
  onScroll?: (container: HTMLDivElement) => void;
  onViewportReady?: (container: HTMLDivElement) => void;
  className?: string;
  isFallback?: boolean;
  fallbackMessage?: string;
}

export const PdfViewer: React.FC<Props> = ({
  url,
  page,
  scale,
  title,
  onTotalPages,
  onPageChange,
  onScroll,
  onViewportReady,
  className = '',
  isFallback = false,
  fallbackMessage,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pdfDocRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null);
  const renderTaskRef = useRef<any>(null);
  const renderReadyRef = useRef(false);
  const lastRenderedPageRef = useRef(page);
  const navigationRef = useRef({ page, onPageChange, onViewportReady });
  navigationRef.current = { page, onPageChange, onViewportReady };

  useEffect(() => {
    const container = containerRef.current;
    if (!container || isFallback) return;
    return attachWheelPageNavigation(container, () => ({
      page: navigationRef.current.page,
      totalPages: pdfDocRef.current?.numPages ?? 0,
      ready: renderReadyRef.current,
    }), (nextPage) => navigationRef.current.onPageChange?.(nextPage));
  }, [isFallback]);

  // 1. 加载 PDF 基础文档
  useEffect(() => {
    if (isFallback) {
      setLoading(false);
      return;
    }

    let isMounted = true;
    pdfDocRef.current = null;
    renderReadyRef.current = false;
    lastRenderedPageRef.current = page;
    setLoading(true);
    setError(null);

    const loadingTask = pdfjsLib.getDocument({
      url,
      disableAutoFetch: true,
      disableStream: true,
      rangeChunkSize: 64 * 1024,
      cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/cmaps/',
      cMapPacked: true,
    });

    loadingTask.promise
      .then((pdf) => {
        if (!isMounted) return;
        pdfDocRef.current = pdf;
        if (onTotalPages) {
          onTotalPages(pdf.numPages);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error(`[PdfViewer] 加载 PDF 失败 (${title}):`, err);
        setError(err.message || '加载 PDF 文档失败');
        setLoading(false);
      });

    return () => {
      isMounted = false;
      loadingTask.destroy();
    };
  }, [url, isFallback]);

  // 2. 渲染指定页码
  useEffect(() => {
    if (isFallback || !pdfDocRef.current || !canvasRef.current) return;

    let isCancelled = false;
    renderReadyRef.current = false;
    const doc = pdfDocRef.current;
    const canvas = canvasRef.current;
    const targetPage = Math.min(Math.max(1, page), doc.numPages);

    doc.getPage(targetPage).then((pageObj) => {
      if (isCancelled) return;

      // 如果有之前的渲染任务在执行，先安全取消
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch (_) {}
      }

      const viewport = pageObj.getViewport({ scale });
      const context = canvas.getContext('2d');
      if (!context) return;

      // 适配高清屏幕 (Retina / 2x display)
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      context.setTransform(dpr, 0, 0, dpr, 0, 0);

      const renderContext = {
        canvasContext: context,
        viewport,
      };

      const task = pageObj.render(renderContext);
      renderTaskRef.current = task;

      task.promise
        .then(() => {
          if (isCancelled) return;
          renderTaskRef.current = null;
          // 向后翻页从页顶开始，向前翻页从页底继续，缩放时保留滚动位置。
          if (containerRef.current && targetPage !== lastRenderedPageRef.current) {
            containerRef.current.scrollTop = targetPage < lastRenderedPageRef.current
              ? containerRef.current.scrollHeight
              : 0;
          }
          lastRenderedPageRef.current = targetPage;
          renderReadyRef.current = true;
          if (containerRef.current) {
            navigationRef.current.onViewportReady?.(containerRef.current);
          }
        })
        .catch((err) => {
          if (err.name !== 'RenderingCancelledException') {
            console.error('[PdfViewer] 页面渲染错误:', err);
          }
        });
    });

    return () => {
      isCancelled = true;
      renderReadyRef.current = false;
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch (_) {}
      }
    };
  }, [page, scale, loading, isFallback]);

  if (isFallback) {
    return (
      <div className={`flex flex-col items-center justify-center p-8 text-center bg-slate-100/50 rounded-xl border border-dashed border-slate-300 ${className}`}>
        <AlertCircle className="w-10 h-10 text-amber-500 mb-3" />
        <h4 className="font-semibold text-slate-800 mb-1">{title} 暂未就绪</h4>
        <p className="text-sm text-slate-500 max-w-sm">
          {fallbackMessage || '论文尚未开始翻译或仍在翻译中，点击顶部的“开始翻译”即可生成中文版本。'}
        </p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={(event) => onScroll?.(event.currentTarget)}
      className={`relative overflow-auto overscroll-contain bg-slate-200/60 p-4 min-h-0 rounded-xl select-none ${className}`}
    >
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/70 backdrop-blur-sm z-10">
          <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
          <span className="ml-2 text-sm text-slate-600 font-medium">正在加载 {title}...</span>
        </div>
      )}

      {error ? (
        <div className="flex flex-col items-center justify-center p-12 text-center text-rose-600">
          <AlertCircle className="w-10 h-10 mb-2" />
          <p className="text-sm font-semibold">{error}</p>
        </div>
      ) : (
        <div className="w-max mx-auto shadow-xl bg-white border border-slate-300 rounded overflow-hidden">
          <canvas ref={canvasRef} className="block" />
        </div>
      )}
    </div>
  );
};
