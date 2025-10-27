"use client";

import { Skeleton, SkeletonText } from "../../components/LoadingStates";

export function VerseReliabilitySkeleton(): JSX.Element {
  return (
    <div className="card stack-sm verse-skeleton" aria-hidden="true">
      <Skeleton width="60%" height="1.5rem" />
      <Skeleton width="80%" height="1rem" />
      <Skeleton width="40%" height="0.875rem" />
      <div className="stack-sm">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="verse-skeleton__item stack-xs">
            <SkeletonText lines={2} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function VerseResearchSkeleton(): JSX.Element {
  return (
    <div className="stack-md" aria-hidden="true">
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="card stack-sm verse-skeleton__panel">
          <Skeleton width="70%" height="1.25rem" />
          <SkeletonText lines={3} />
        </div>
      ))}
    </div>
  );
}
