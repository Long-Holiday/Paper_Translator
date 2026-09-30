import React, { useRef, useState } from 'react';
import { UploadCloud, Plus, Loader2 } from 'lucide-react';
import { uploadPaper } from '../api/papers';
import { Paper } from '../types/paper';

interface Props {
  onSuccess: (paper: Paper) => void;
}

export const ImportButton: React.FC<Props> = ({ onSuccess }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('请选择 PDF 格式的论文文件');
      return;
    }
    setErrorMsg(null);
    setUploading(true);
    try {
      const paper = await uploadPaper(file);
      onSuccess(paper);
    } catch (err: any) {
      setErrorMsg(err.message || '上传论文失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFile(file);
    }
  };

  return (
    <div>
      <input
        type="file"
        ref={fileInputRef}
        onChange={onChange}
        accept=".pdf"
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="inline-flex items-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold rounded-xl shadow-md shadow-sky-600/20 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
      >
        {uploading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Plus className="w-4 h-4" />
        )}
        <span>{uploading ? '正在解析导入...' : '导入论文 PDF'}</span>
      </button>

      {errorMsg && (
        <div className="fixed bottom-6 right-6 z-50 p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl shadow-lg text-sm flex items-center gap-2">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="ml-2 font-bold">×</button>
        </div>
      )}
    </div>
  );
};
