import React from 'react';
import ReactDOM from 'react-dom/client';
import * as pdfjsLib from 'pdfjs-dist';
// Vite 原生支持将 worker 解析为本地 URL，完全支持离线本地运行
// @ts-ignore
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import App from './App';
import './index.css';

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
