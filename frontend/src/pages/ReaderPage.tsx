import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getPaper, updateReadingPosition, startTranslate, deletePaper } from '../api/papers';
import { useTranslationUpdates } from '../hooks/useTranslationUpdates';
import { Paper } from '../types/paper';
import { DualPdfViewer } from '../components/DualPdfViewer';
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Loader2,
  RefreshCw,
  Trash2,
} from 'lucide-react';

export const ReaderPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const paperId = Number(id);

  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [navigationKey, setNavigationKey] = useState(0);
  const [scale, setScale] = useState<number>(1.2);
  const [syncEnabled, setSyncEnabled] = useState<boolean>(true);
  const [isDeleting, setIsDeleting] = useState(false);

  // 防抖定时器保存阅读进度
  const saveTimerRef = useRef<any>(null);

  // 1. 初始化拉取论文详情并恢复阅读位置
  const loadPaper = useCallback(async () => {
    try {
      const data = await getPaper(paperId);
      setPaper(data);
      if (data.last_read_page) {
        setCurrentPage(data.last_read_page);
      }
      if (data.page_count) {
        setTotalPages(data.page_count);
      }
    } catch (err) {
      console.error('加载论文失败:', err);
    } finally {
      setLoading(false);
    }
  }, [paperId]);

  useEffect(() => {
    loadPaper();
  }, [loadPaper]);

  // 2. 每秒轮询翻译进度，完成后自动停止。
  useTranslationUpdates(paper && paper.id === paperId ? [paper] : [], ({ papers, removed_ids }) => {
    if (removed_ids.includes(paperId)) {
      setPaper(null);
    } else {
      const updated = papers.find((item) => item.id === paperId);
      if (updated) setPaper(updated);
    }
  });

  // 3. 防抖自动保存最后阅读页
  const debouncedSavePosition = useCallback(
    (page: number) => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = setTimeout(() => {
        updateReadingPosition(paperId, page).catch((err) => {
          console.warn('保存阅读位置失败:', err);
        });
      }, 1000);
    },
    [paperId]
  );

  const handlePageChange = (newPage: number, fromScroll = false) => {
    const validPage = Math.max(1, Math.min(newPage, totalPages || 9999));
    setCurrentPage(validPage);
    if (!fromScroll) setNavigationKey((key) => key + 1);
    debouncedSavePosition(validPage);
  };

  // 4. 键盘左右方向键监听翻页
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        e.preventDefault();
        handlePageChange(currentPage - 1);
      } else if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
        e.preventDefault();
        handlePageChange(currentPage + 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentPage, totalPages]);

  const handleZoomIn = () => setScale((s) => Math.min(2.5, +(s + 0.15).toFixed(2)));
  const handleZoomOut = () => setScale((s) => Math.max(0.6, +(s - 0.15).toFixed(2)));
  const handleResetZoom = () => setScale(1.2);

  const handleStartTranslate = async () => {
    try {
      await startTranslate(paperId);
      setPaper((prev) => (prev ? { ...prev, translation_status: 'queued', translation_progress: 0, translation_error: null } : null));
    } catch (err: any) {
      alert(`启动翻译失败: ${err.message}`);
    }
  };

  const handleDeleteCurrentPaper = async () => {
    if (!paper) return;
    if (window.confirm(`确定要彻底删除当前正在阅读的论文《${paper.title}》吗？\n删除后将自动返回目录。`)) {
      setIsDeleting(true);
      try {
        await deletePaper(paperId);
        navigate('/');
      } catch (err: any) {
        alert(`删除失败: ${err.message}`);
        setIsDeleting(false);
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white text-black">
        <Loader2 className="w-8 h-8 animate-spin text-sky-600 mr-2" />
        <span>正在载入双栏阅读器...</span>
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-white text-black p-4">
        <h2 className="text-lg font-bold mb-2">未找到该论文</h2>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 text-black rounded-lg text-sm"
        >
          返回论文目录
        </button>
      </div>
    );
  }

  return (
    <div className="reader-screen h-screen flex flex-col bg-white text-black overflow-hidden select-none">
      {/* 顶部控制栏 */}
      <header className="reader-toolbar h-12 bg-white border-b border-slate-100 px-3 sm:px-4 flex items-center justify-between gap-3 shrink-0 z-20">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
          <button
            onClick={() => navigate('/')}
            className="reader-control inline-flex shrink-0 items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-black rounded-lg"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">返回目录</span>
          </button>
          <div className="h-4 w-px bg-slate-200 hidden sm:block" />
          <h2 className="text-sm font-semibold tracking-tight text-black truncate min-w-0" title={paper.title}>
            {paper.title}
          </h2>
        </div>

        {/* 缩放、翻页控制与删除按钮 */}
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          {/* 缩放控制器 */}
          <div className="reader-control-group flex items-center rounded-lg p-0.5">
            <button
              onClick={handleZoomOut}
              className="reader-control p-1.5 text-black rounded-md"
              title="缩小"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={handleResetZoom}
              className="reader-control min-w-12 px-2 py-1.5 text-xs font-medium tabular-nums text-black rounded-md"
              title="重置缩放"
            >
              {Math.round(scale * 100)}%
            </button>
            <button
              onClick={handleZoomIn}
              className="reader-control p-1.5 text-black rounded-md"
              title="放大"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>

          {/* 页码与翻页器 */}
          <div className="reader-control-group flex items-center gap-0.5 rounded-lg px-1 py-0.5 text-xs">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="reader-control p-1.5 text-black rounded-md disabled:opacity-25"
              title="上一页 (←)"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="tabular-nums px-1 whitespace-nowrap">
              <input
                type="number"
                min={1}
                max={totalPages || 1}
                value={currentPage}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  if (!isNaN(val)) handlePageChange(val);
                }}
                className="reader-page-input w-9 bg-white text-center text-black rounded-md border border-transparent focus:outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-100 py-1"
              />
              <span className="text-black opacity-60 ml-1">/ {totalPages || 1}</span>
            </span>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="reader-control p-1.5 text-black rounded-md disabled:opacity-25"
              title="下一页 (→)"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* 阅读页顶栏删除按钮 */}
          <button
            onClick={handleDeleteCurrentPaper}
            disabled={isDeleting}
            className="reader-control reader-delete inline-flex items-center gap-1.5 px-2.5 py-2 text-xs font-medium text-black rounded-lg disabled:opacity-40"
            title="删除当前论文"
          >
            {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">删除</span>
          </button>
        </div>
      </header>

      {/* 主体双栏渲染区 */}
      <main className="flex-1 min-h-0 bg-white p-0 overflow-hidden">
        <DualPdfViewer
          paper={paper}
          currentPage={currentPage}
          navigationKey={navigationKey}
          scale={scale}
          syncEnabled={syncEnabled}
          onTotalPages={(total) => setTotalPages(total)}
          onPageChange={(page) => handlePageChange(page, true)}
          onStartTranslate={handleStartTranslate}
        />
      </main>

      {/* 底部快捷状态与翻页提示 */}
      <footer className="h-7 bg-white border-t border-slate-100 px-3 sm:px-4 flex items-center justify-between gap-3 text-[11px] text-black shrink-0">
        <div>
          <span className="flex items-center gap-2"><span className="opacity-60">连续滚动阅读</span><span className="hidden sm:inline-flex items-center gap-1"><kbd className="reader-shortcut">←</kbd><kbd className="reader-shortcut">→</kbd><kbd className="reader-shortcut">空格</kbd><span className="opacity-60 ml-1">翻页</span></span></span>
        </div>
        <div className="flex items-center gap-3">
          {paper.translation_status === 'translating' && (
            <span className="flex items-center gap-1 text-black">
              <RefreshCw className="w-3 h-3 animate-spin" />
              后台翻译进度: {paper.translation_progress}%
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap tabular-nums"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" aria-hidden="true" /><span className="opacity-60">自动保存 · 第 {currentPage} 页</span></span>
        </div>
      </footer>
    </div>
  );
};
