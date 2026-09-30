export const PAGE_GAP = 12;
export const VIEWER_PADDING = 0;

export function pageTop(heights: number[], page: number, scale: number) {
  return VIEWER_PADDING + heights.slice(0, page - 1).reduce((top, height) => top + height * scale + PAGE_GAP, 0);
}

// 页间距不随缩放改变，按当前页内的位置恢复视口。
export function scaledScrollTop(heights: number[], top: number, previousScale: number, nextScale: number) {
  let previousTop = VIEWER_PADDING;
  let nextTop = VIEWER_PADDING;
  for (const height of heights) {
    if (top < previousTop + height * previousScale) {
      return Math.max(0, nextTop + (top - previousTop) * nextScale / previousScale);
    }
    if (top < previousTop + height * previousScale + PAGE_GAP) {
      return nextTop + height * nextScale + (top - previousTop - height * previousScale);
    }
    previousTop += height * previousScale + PAGE_GAP;
    nextTop += height * nextScale + PAGE_GAP;
  }
  return Math.max(0, nextTop + top - previousTop);
}
