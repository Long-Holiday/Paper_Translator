type Side = 'original' | 'translated';

interface Viewport {
  element: HTMLElement;
  ready: boolean;
  maxTop: number;
  expectedTop?: number;
}

export function createScrollSync(_initialPage: number, initialScale: number) {
  const viewports = new Map<Side, Viewport>();
  let navigationKey = 0;
  let scale = initialScale;
  let progress = 0;

  const applyProgress = (viewport: Viewport) => {
    const maxTop = Math.max(0, viewport.element.scrollHeight - viewport.element.clientHeight);
    viewport.maxTop = maxTop;
    viewport.expectedTop = progress * maxTop;
    viewport.element.scrollTop = viewport.expectedTop;
    // 浏览器可能对 scrollTop 取整或限幅，使用实际落点屏蔽程序滚动的回调。
    viewport.expectedTop = viewport.element.scrollTop;
  };

  return {
    setView(_nextPage: number, nextScale: number, nextNavigationKey = 0) {
      if (nextNavigationKey === navigationKey && nextScale === scale) return;
      navigationKey = nextNavigationKey;
      scale = nextScale;
      // 缩放或显式跳页时，等待两栏的新布局；自然滚动更新页码不会打断同步。
      viewports.forEach((viewport) => { viewport.ready = false; });
    },

    ready(side: Side, element: HTMLElement) {
      const existing = viewports.get(side);
      const viewport: Viewport = { element, ready: true, maxTop: Math.max(0, element.scrollHeight - element.clientHeight) };
      const hasReadyPeer = [...viewports.entries()].some(([peerSide, peer]) => peerSide !== side && peer.ready);
      viewports.set(side, viewport);
      if (existing?.maxTop === 0) {
        applyProgress(viewport);
      } else if (!hasReadyPeer || existing?.ready) {
        const maxTop = Math.max(0, element.scrollHeight - element.clientHeight);
        if (maxTop) progress = Math.max(0, Math.min(1, element.scrollTop / maxTop));
        viewports.forEach((peer, peerSide) => {
          if (peerSide !== side && peer.ready) applyProgress(peer);
        });
      } else {
        applyProgress(viewport);
      }
    },

    scroll(side: Side, element: HTMLElement) {
      const source = viewports.get(side);
      if (!source?.ready || source.element !== element) return;
      if (source.expectedTop !== undefined && Math.abs(element.scrollTop - source.expectedTop) <= 1) return;
      source.expectedTop = undefined;

      const maxTop = Math.max(0, element.scrollHeight - element.clientHeight);
      source.maxTop = maxTop;
      if (!maxTop) return;
      progress = Math.max(0, Math.min(1, element.scrollTop / maxTop));
      viewports.forEach((viewport, targetSide) => {
        if (targetSide !== side && viewport.ready) applyProgress(viewport);
      });
    },
  };
}
