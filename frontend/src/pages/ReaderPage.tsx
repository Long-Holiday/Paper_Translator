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

  // 2. 翻译进度通过长连接更新，完成后自动停止订阅。
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

  const handlePageChange = (newPage: number) => {
    const validPage = Math.max(1, Math.min(newPage, totalPages || 9999));
    setCurrentPage(validPage);
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
      setPaper((prev) => (prev ? { ...prev, translation_status: 'queued' } : null));
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
      <div className="min-h-screen flex items-center justify-center bg-slate-100 text-slate-600">
        <Loader2 className="w-8 h-8 animate-spin text-sky-600 mr-2" />
        <span>正在载入双栏阅读器...</span>
      </div>
    );
  }

  if (!paper) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-100 text-slate-600 p-4">
        <h2 className="text-lg font-bold mb-2">未找到该论文</h2>
        <button
          onClick={() => navigate('/')}
          className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm"
        >
          返回论文目录
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-slate-900 text-slate-100 overflow-hidden select-none">
      {/* 顶部控制栏 */}
      <header className="h-14 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between shrink-0 z-20">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>返回目录</span>
          </button>
          <div className="h-4 w-px bg-slate-700 hidden sm:block" />
          <h2 className="text-sm font-semibold text-slate-200 truncate max-w-xs md:max-w-md lg:max-w-lg" title={paper.title}>
            {paper.title}
          </h2>
        </div>

        {/* 缩放、翻页控制与删除按钮 */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* 缩放控制器 */}
          <div className="flex items-center bg-slate-800 rounded-lg p-0.5 border border-slate-700">
            <button
              onClick={handleZoomOut}
              className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors"
              title="缩小"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={handleResetZoom}
              className="px-2 py-1 text-xs font-mono font-medium text-slate-300 hover:text-white"
              title="重置缩放"
            >
              {Math.round(scale * 100)}%
            </button>
            <button
              onClick={handleZoomIn}
              className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition-colors"
              title="放大"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>

          {/* 页码与翻页器 */}
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg px-2 py-1 border border-slate-700 text-xs">
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="p-1 text-slate-300 hover:text-white disabled:opacity-30 disabled:hover:text-slate-300 transition-colors"
              title="上一页 (←)"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-mono px-1">
              <input
                type="number"
                min={1}
                max={totalPages || 1}
                value={currentPage}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  if (!isNaN(val)) handlePageChange(val);
                }}
                className="w-10 bg-slate-900 text-center text-white rounded border border-slate-700 focus:outline-none focus:border-sky-500 py-0.5"
              />
              <span className="text-slate-400 ml-1">/ {totalPages || 1}</span>
            </span>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="p-1 text-slate-300 hover:text-white disabled:opacity-30 disabled:hover:text-slate-300 transition-colors"
              title="下一页 (→)"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* 阅读页顶栏删除按钮 */}
          <button
            onClick={handleDeleteCurrentPaper}
            disabled={isDeleting}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg border border-slate-700 hover:border-rose-500/30 transition-colors"
            title="删除当前论文"
          >
            {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">删除</span>
          </button>
        </div>
      </header>

      {/* 主体双栏渲染区 */}
      <main className="flex-1 min-h-0 bg-slate-950 p-3 overflow-hidden">
        <DualPdfViewer
          paper={paper}
          currentPage={currentPage}
          scale={scale}
          syncEnabled={syncEnabled}
          onTotalPages={(total) => setTotalPages(total)}
          onPageChange={handlePageChange}
          onStartTranslate={handleStartTranslate}
        />
      </main>

      {/* 底部快捷状态与翻页提示 */}
      <footer className="h-8 bg-slate-900 border-t border-slate-800 px-4 flex items-center justify-between text-[11px] text-slate-400 shrink-0">
        <div>
          <span>滚动翻页：页底下滚 / 页顶上滚 · 快捷键：← / → / 空格</span>
        </div>
        <div className="flex items-center gap-3">
          {paper.translation_status === 'translating' && (
            <span className="flex items-center gap-1 text-sky-400">
              <RefreshCw className="w-3 h-3 animate-spin" />
              后台翻译进度: {paper.translation_progress}%
            </span>
          )}
          <span>自动保存阅读进度：已保存至第 {currentPage} 页</span>
        </div>
      </footer>
    </div>
  );
};
