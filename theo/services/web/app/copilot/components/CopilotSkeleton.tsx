"use client";

import { Skeleton, SkeletonText } from "../../components/LoadingStates";

export function CopilotSkeleton(): JSX.Element {
  return (
    <div className="stack-lg" aria-hidden="true">
      <div className="card stack-sm copilot-skeleton__section">
        <Skeleton width="50%" height="1.5rem" />
        <SkeletonText lines={3} />
      </div>
      <div className="card stack-sm copilot-skeleton__section">
        <Skeleton width="60%" height="1.25rem" />
        <SkeletonText lines={4} />
      </div>
    </div>
  );
}
