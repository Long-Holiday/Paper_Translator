interface ReadingState {
  page: number;
  totalPages: number;
  ready: boolean;
}

// 保留页内原生滚动，只在页边界累积一次明确的纵向滚动后翻页。
export function attachWheelPageNavigation(
  container: HTMLElement,
  getState: () => ReadingState,
  onPageChange: (page: number) => void,
): () => void {
  let accumulatedDelta = 0;
  let lastEventTime = -Infinity;
  let lastPageChangeTime = -Infinity;

  const handleWheel = (event: WheelEvent) => {
    if (event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY) || !event.deltaY) return;

    const { page, totalPages, ready } = getState();
    const direction = Math.sign(event.deltaY);
    const atBoundary = direction > 0
      ? container.scrollTop + container.clientHeight >= container.scrollHeight - 2
      : container.scrollTop <= 2;
    const nextPage = page + direction;

    if (!atBoundary || nextPage < 1 || nextPage > totalPages) {
      accumulatedDelta = 0;
      return;
    }

    event.preventDefault();
    const now = event.timeStamp;
    if (!ready || now - lastPageChangeTime < 600) {
      accumulatedDelta = 0;
      return;
    }

    if (now - lastEventTime > 200 || Math.sign(accumulatedDelta) !== direction) {
      accumulatedDelta = 0;
    }
    lastEventTime = now;
    const delta = event.deltaMode === 1
      ? event.deltaY * 16
      : event.deltaMode === 2
        ? event.deltaY * container.clientHeight
        : event.deltaY;
    accumulatedDelta += delta;

    if (Math.abs(accumulatedDelta) >= 60) {
      accumulatedDelta = 0;
      lastPageChangeTime = now;
      onPageChange(nextPage);
    }
  };

  container.addEventListener('wheel', handleWheel, { passive: false });
  return () => container.removeEventListener('wheel', handleWheel);
}
