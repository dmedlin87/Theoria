import { memo, type ComponentType } from "react";

/**
 * Enhanced memo wrapper with display name preservation for better debugging
 * 
 * @example
 * const MyComponent = memoComponent(
 *   ({ id, name }: Props) => <div>{name}</div>,
 *   (prev, next) => prev.id === next.id && prev.name === next.name
 * );
 */
export function memoComponent<P extends object>(
  Component: ComponentType<P>,
  areEqual?: (prevProps: Readonly<P>, nextProps: Readonly<P>) => boolean
): ComponentType<P> {
  const MemoizedComponent = memo(Component, areEqual);
  
  // Preserve display name for React DevTools
  const displayName = Component.displayName || Component.name || "Component";
  MemoizedComponent.displayName = `Memo(${displayName})`;
  
  return MemoizedComponent;
}

/**
 * Custom comparison function for props with primitive values
 * Useful for components that receive simple props like strings, numbers, booleans
 */
export function shallowEqual<P extends Record<string, unknown>>(
  prevProps: Readonly<P>,
  nextProps: Readonly<P>
): boolean {
  const prevKeys = Object.keys(prevProps);
  const nextKeys = Object.keys(nextProps);
  
  if (prevKeys.length !== nextKeys.length) {
    return false;
  }
  
  return prevKeys.every((key) => {
    return Object.is(prevProps[key], nextProps[key]);
  });
}
