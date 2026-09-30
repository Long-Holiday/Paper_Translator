import { useEffect, useRef } from 'react';
import { PaperUpdates, subscribeTranslationUpdates } from '../api/papers';
import { Paper } from '../types/paper';

export function useTranslationUpdates(
  papers: Paper[],
  onUpdate: (updates: PaperUpdates) => void
) {
  const callback = useRef(onUpdate);
  useEffect(() => {
    callback.current = onUpdate;
  }, [onUpdate]);

  const activeIds = papers
    .filter((paper) => ['queued', 'translating'].includes(paper.translation_status))
    .map((paper) => paper.id)
    .sort((a, b) => a - b)
    .join(',');

  useEffect(() => {
    if (!activeIds) return;
    return subscribeTranslationUpdates(
      activeIds.split(',').map(Number),
      (updates) => callback.current(updates)
    );
  }, [activeIds]);
}
