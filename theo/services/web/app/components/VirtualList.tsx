"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef } from "react";
import type { ReactNode, HTMLAttributes } from "react";

interface VirtualListProps<T> {
  items: readonly T[];
  renderItem: (item: T, index: number) => ReactNode;
  estimateSize?: (item: T, index: number) => number;
  overscan?: number;
  itemKey?: (item: T, index: number) => string | number;
  emptyState?: ReactNode;
  containerProps?: Omit<HTMLAttributes<HTMLDivElement>, "children">;
  scrollToIndex?: number | null;
}

const DEFAULT_ESTIMATE = 180;

export default function VirtualList<T>({
  items,
  renderItem,
  estimateSize,
  overscan = 8,
  itemKey,
  emptyState,
  containerProps,
  scrollToIndex,
}: VirtualListProps<T>): JSX.Element {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const getEstimate = useMemo(
    () =>
      estimateSize
        ? (index: number) => estimateSize(items[index], index)
        : () => DEFAULT_ESTIMATE,
    [estimateSize, items],
  );

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: getEstimate,
    overscan,
  });

  if (items.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  const virtualItems = virtualizer.getVirtualItems();
  const totalSize = virtualizer.getTotalSize();
  const measureElement = typeof window === "undefined" ? undefined : virtualizer.measureElement;

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) {
      return;
    }
    viewport.style.height = `${totalSize}px`;
  }, [totalSize]);

  useEffect(() => {
    if (scrollToIndex == null) {
      return;
    }
    virtualizer.scrollToIndex(scrollToIndex, { align: "start" });
  }, [scrollToIndex, virtualizer]);

  const { className, style: _ignoredStyle, ...restContainerProps } = containerProps ?? {};
  const combinedClassName = className ? `virtual-list ${className}` : "virtual-list";

  return (
    <div {...restContainerProps} ref={scrollRef} className={combinedClassName}>
      <div ref={viewportRef} className="virtual-list__viewport">
        {virtualItems.map((virtualRow) => {
          const index = virtualRow.index;
          const item = items[index];
          const key = itemKey ? itemKey(item, index) : virtualRow.key;
          const setNodeRef = (node: HTMLDivElement | null) => {
            if (!node) {
              return;
            }
            if (measureElement) {
              measureElement(node);
            }
            node.style.transform = `translateY(${virtualRow.start}px)`;
          };

          return (
            <div
              key={key}
              ref={setNodeRef}
              data-index={index}
              className="virtual-list__item"
            >
              {renderItem(item, index)}
            </div>
          );
        })}
      </div>
    </div>
  );
}
