type Side = 'original' | 'translated';

interface Viewport {
  element: HTMLElement;
  ready: boolean;
  expectedTop?: number;
}

export function createScrollSync(initialPage: number, initialScale: number) {
  const viewports = new Map<Side, Viewport>();
  let page = initialPage;
  let scale = initialScale;
  let progress = 0;

  const applyProgress = (viewport: Viewport) => {
    const maxTop = Math.max(0, viewport.element.scrollHeight - viewport.element.clientHeight);
    viewport.expectedTop = progress * maxTop;
    viewport.element.scrollTop = viewport.expectedTop;
    // 浏览器可能对 scrollTop 取整或限幅，使用实际落点屏蔽程序滚动的回调。
    viewport.expectedTop = viewport.element.scrollTop;
  };

  return {
    setView(nextPage: number, nextScale: number) {
      if (nextPage === page && nextScale === scale) return;
      if (nextPage !== page) progress = nextPage < page ? 1 : 0;
      page = nextPage;
      scale = nextScale;
      // 两栏渲染完成的时间不同，禁止旧页面布局的滚动覆盖新页位置。
      viewports.forEach((viewport) => { viewport.ready = false; });
    },

    ready(side: Side, element: HTMLElement) {
      const viewport: Viewport = { element, ready: true };
      viewports.set(side, viewport);
      applyProgress(viewport);
    },

    scroll(side: Side, element: HTMLElement) {
      const source = viewports.get(side);
      if (!source?.ready || source.element !== element) return;
      if (source.expectedTop !== undefined && Math.abs(element.scrollTop - source.expectedTop) <= 1) return;
      source.expectedTop = undefined;

      const maxTop = Math.max(0, element.scrollHeight - element.clientHeight);
      if (!maxTop) return;
      progress = Math.max(0, Math.min(1, element.scrollTop / maxTop));
      viewports.forEach((viewport, targetSide) => {
        if (targetSide !== side && viewport.ready) applyProgress(viewport);
      });
    },
  };
}
