import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { Loader2, AlertCircle } from 'lucide-react';
import { pageTop, scaledScrollTop } from './pdfLayout';

interface Props {
  url: string;
  page: number;
  navigationKey?: number;
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

interface PageSize { width: number; height: number }

// 保留每页的完整占位，只渲染视口及附近的画布，避免长论文占用过多显存。
const PdfCanvas: React.FC<{
  doc: pdfjsLib.PDFDocumentProxy;
  number: number;
  scale: number;
  size: PageSize;
  container: React.RefObject<HTMLDivElement>;
}> = ({ doc, number, scale, size, container }) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), {
      root: container.current,
      rootMargin: '150% 0px',
    });
    if (wrapperRef.current) observer.observe(wrapperRef.current);
    return () => observer.disconnect();
  }, [container]);

  useEffect(() => {
    if (!visible || !canvasRef.current) return;
    let cancelled = false;
    let task: pdfjsLib.RenderTask | undefined;
    const canvas = canvasRef.current;
    setError(false);
    const render = async () => {
      try {
        const pdfPage = await doc.getPage(number);
        if (cancelled) return;
        const viewport = pdfPage.getViewport({ scale });
        const context = canvas.getContext('2d');
        if (!context) return;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);
        task = pdfPage.render({
          canvasContext: context,
          viewport,
          transform: dpr === 1 ? undefined : [dpr, 0, 0, dpr, 0, 0],
        });
        await task.promise;
      } catch (err: any) {
        if (!cancelled && err.name !== 'RenderingCancelledException') setError(true);
      }
    };
    void render();
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [doc, number, scale, visible]);

  return (
    <div ref={wrapperRef} data-page={number} className="relative shrink-0 bg-white"
      style={{ width: size.width * scale, height: size.height * scale }}>
      {visible && <canvas key={scale} ref={canvasRef} className="block w-full h-full" />}
      {error && <p className="absolute inset-0 flex items-center justify-center text-sm text-rose-600">第 {number} 页加载失败</p>}
    </div>
  );
};

export const PdfViewer: React.FC<Props> = ({
  url, page, navigationKey = 0, scale, title, onTotalPages, onPageChange,
  onScroll, onViewportReady, className = '', isFallback = false, fallbackMessage,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [document, setDocument] = useState<{ doc: pdfjsLib.PDFDocumentProxy; sizes: PageSize[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const callbacks = useRef({ page, onTotalPages, onPageChange, onScroll, onViewportReady });
  callbacks.current = { page, onTotalPages, onPageChange, onScroll, onViewportReady };
  const lastPage = useRef(page);
  const lastScale = useRef(scale);
  const frame = useRef<number>();

  useEffect(() => {
    if (isFallback) { setLoading(false); return; }
    let cancelled = false;
    setDocument(null);
    setLoading(true);
    setError(null);
    const task = pdfjsLib.getDocument({
      url,
      cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/cmaps/',
      cMapPacked: true,
    });
    void (async () => {
      try {
        const doc = await task.promise;
        const sizes: PageSize[] = [];
        // 顺序读取页面尺寸，避免一次对长文档发起大量并发任务。
        for (let number = 1; number <= doc.numPages; number++) {
          if (cancelled) return;
          const pdfPage = await doc.getPage(number);
          const viewport = pdfPage.getViewport({ scale: 1 });
          sizes.push({ width: viewport.width, height: viewport.height });
        }
        if (cancelled) return;
        callbacks.current.onTotalPages?.(doc.numPages);
        setDocument({ doc, sizes });
        setLoading(false);
      } catch (err: any) {
        if (!cancelled) { setError(err.message || '加载 PDF 文档失败'); setLoading(false); }
      }
    })();
    return () => { cancelled = true; void task.destroy(); };
  }, [url, isFallback]);

  // 只有显式翻页才跳转；滚动产生的页码更新不会把视口拉回页顶。
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container || !document) return;
    const target = Math.min(Math.max(1, callbacks.current.page), document.doc.numPages);
    container.scrollTop = pageTop(document.sizes.map((size) => size.height), target, scale);
    lastPage.current = target;
    lastScale.current = scale;
    callbacks.current.onViewportReady?.(container);
  }, [document, navigationKey]);

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container || !document || scale === lastScale.current) return;
    const ratio = scale / lastScale.current;
    container.scrollTop = scaledScrollTop(document.sizes.map((size) => size.height), container.scrollTop, lastScale.current, scale);
    container.scrollLeft *= ratio;
    lastScale.current = scale;
    callbacks.current.onViewportReady?.(container);
  }, [scale, document]);

  useEffect(() => () => { if (frame.current !== undefined) cancelAnimationFrame(frame.current); }, []);

  const handleScroll = (container: HTMLDivElement) => {
    callbacks.current.onScroll?.(container);
    if (frame.current !== undefined) cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      // 视口上部进入下一页时更新阅读页码，跨页过程中保持原生滚动。
      const probe = container.getBoundingClientRect().top + Math.min(100, container.clientHeight / 4);
      const pages = container.querySelectorAll<HTMLElement>('[data-page]');
      let low = 0;
      let high = pages.length - 1;
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        if (pages[middle].getBoundingClientRect().top <= probe) low = middle;
        else high = middle - 1;
      }
      const visiblePage = Number(pages[low]?.dataset.page);
      if (visiblePage && visiblePage !== lastPage.current) {
        lastPage.current = visiblePage;
        callbacks.current.onPageChange?.(visiblePage);
      }
    });
  };

  if (isFallback) return (
    <div className={`flex flex-col items-center justify-center p-8 text-center bg-white text-black ${className}`}>
      <AlertCircle className="w-10 h-10 text-amber-500 mb-3" />
      <h4 className="font-semibold text-black mb-1">{title} 暂未就绪</h4>
      <p className="text-sm text-black max-w-sm">{fallbackMessage || '论文尚未开始翻译或仍在翻译中，点击顶部的“开始翻译”即可生成中文版本。'}</p>
    </div>
  );

  return (
    <div ref={containerRef} onScroll={(event) => handleScroll(event.currentTarget)}
      className={`relative overflow-auto overscroll-contain bg-white text-black p-0 min-h-0 select-none ${className}`}
      style={{ overflowAnchor: 'none' }}>
      {loading && <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
        <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
        <span className="ml-2 text-sm text-black font-medium">正在加载 {title}...</span>
      </div>}
      {error ? <div className="flex flex-col items-center justify-center p-12 text-center text-rose-600">
        <AlertCircle className="w-10 h-10 mb-2" /><p className="text-sm font-semibold">{error}</p>
      </div> : document && <div className="flex flex-col items-center w-max min-w-full gap-3">
        {document.sizes.map((size, index) => <PdfCanvas key={index} doc={document.doc} number={index + 1}
          scale={scale} size={size} container={containerRef} />)}
      </div>}
    </div>
  );
};
