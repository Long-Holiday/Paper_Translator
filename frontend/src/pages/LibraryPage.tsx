import React, { useEffect, useState, useCallback } from 'react';
import { getPapers, startTranslate, deletePaper } from '../api/papers';
import { useTranslationUpdates } from '../hooks/useTranslationUpdates';
import { Paper } from '../types/paper';
import { Header } from '../components/Header';
import { PaperCard } from '../components/PaperCard';
import { ImportButton } from '../components/ImportButton';
import { ConfigModal } from '../components/ConfigModal';
import { Search, BookOpen, RefreshCw } from 'lucide-react';

export const LibraryPage: React.FC = () => {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const fetchPapers = useCallback(async (keyword?: string) => {
    try {
      const data = await getPapers(keyword);
      setPapers(data);
      return data;
    } catch (err) {
      console.error('获取论文列表失败:', err);
      return [];
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  // 初始加载及搜索变化
  useEffect(() => {
    fetchPapers(search);
  }, [search, fetchPapers]);

  // 活跃任务每秒批量查询进度，任务结束后自动停止轮询。
  useTranslationUpdates(papers, ({ papers: updated, removed_ids }) => {
    const updates = new Map(updated.map((paper) => [paper.id, paper]));
    setPapers((prev) => prev
      .filter((paper) => !removed_ids.includes(paper.id))
      .map((paper) => updates.get(paper.id) ?? paper));
  });

  const handleTranslate = async (id: number) => {
    try {
      await startTranslate(id);
      setPapers((prev) =>
        prev.map((p) =>
          p.id === id ? { ...p, translation_status: 'queued', translation_progress: 0, translation_error: null } : p
        )
      );
    } catch (err: any) {
      alert(`启动翻译失败: ${err.message}`);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deletePaper(id);
      setPapers((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      alert(`删除失败: ${err.message}`);
    }
  };

  const handleImportSuccess = (newPaper: Paper) => {
    setPapers((prev) => [newPaper, ...prev]);
  };

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    fetchPapers(search);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header onOpenSettings={() => setIsSettingsOpen(true)} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 顶部操作区 */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 mb-8">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="搜索论文标题或文件名..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all shadow-sm"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleManualRefresh}
              disabled={isRefreshing}
              className="inline-flex items-center gap-1.5 px-3.5 py-2.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-medium rounded-xl shadow-sm transition-colors disabled:opacity-50"
              title="刷新论文列表"
            >
              <RefreshCw className={`w-4 h-4 text-slate-500 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span>刷新</span>
            </button>
            <ImportButton onSuccess={handleImportSuccess} />
          </div>
        </div>

        {/* 论文列表内容区 */}
        {loading ? (
          <div className="py-20 text-center text-slate-500">
            <div className="w-8 h-8 border-2 border-sky-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
            正在加载论文库...
          </div>
        ) : papers.length === 0 ? (
          <div className="py-20 flex flex-col items-center justify-center text-center bg-white rounded-3xl border border-dashed border-slate-300 p-8 shadow-sm">
            <div className="w-16 h-16 rounded-2xl bg-sky-50 text-sky-600 flex items-center justify-center mb-4">
              <BookOpen className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-800 mb-1">
              {search ? '未找到符合条件的论文' : '论文库为空'}
            </h3>
            <p className="text-sm text-slate-500 max-w-md mb-6">
              {search
                ? '尝试更换搜索关键词，或者重新导入新的 PDF 论文。'
                : '点击右上方的“导入论文 PDF”按钮添加您的英文学术论文，即可一键享受高保真公式翻译与双栏对比阅读。'}
            </p>
            {!search && <ImportButton onSuccess={handleImportSuccess} />}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {papers.map((paper) => (
              <PaperCard
                key={paper.id}
                paper={paper}
                onTranslate={handleTranslate}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </main>

      <ConfigModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
    </div>
  );
};
