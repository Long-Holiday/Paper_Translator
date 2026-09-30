import React from 'react';
import { BookOpen, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';

interface HeaderProps {
  onOpenSettings?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenSettings }) => {
  return (
    <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-sky-500/20 group-hover:scale-105 transition-transform">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight group-hover:text-sky-600 transition-colors">
              Paper Translator
            </h1>
            <p className="text-xs text-slate-500">本地论文双栏对照阅读平台</p>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          {onOpenSettings && (
            <button
              onClick={onOpenSettings}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/80 rounded-lg transition-colors"
              title="翻译设置"
            >
              <Settings className="w-4 h-4" />
              <span>设置</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
