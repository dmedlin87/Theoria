"use client";

import type { WorkflowId } from "./types";

interface WorkflowOption {
  id: WorkflowId;
  label: string;
  description: string;
}

interface WorkflowTabsProps {
  options: WorkflowOption[];
  selected: WorkflowId;
  onSelect: (id: WorkflowId) => void;
}

export default function WorkflowTabs({
  options,
  selected,
  onSelect,
}: WorkflowTabsProps): JSX.Element {
  return (
    <div className="card">
      <h3 className="panel__title mb-3">Workflow</h3>
      <div className="stack-sm">
        {options.map((workflow) => {
          const isActive = workflow.id === selected;
          return (
            <button
              key={workflow.id}
              type="button"
              onClick={() => onSelect(workflow.id)}
              className={`workflow-tab ${isActive ? "workflow-tab--active" : ""}`}
            >
              <div className="stack-xs">
                <strong className="font-semibold">{workflow.label}</strong>
                <span className="text-sm text-muted">{workflow.description}</span>
              </div>
            </button>
          );
        })}
      </div>

      <style jsx>{`
        .workflow-tab {
          width: 100%;
          text-align: left;
          padding: var(--space-2) var(--space-3);
          border-radius: var(--radius-lg);
          border: 1.5px solid var(--color-border-subtle);
          background: var(--color-surface);
          cursor: pointer;
          transition: all var(--transition-base);
        }

        .workflow-tab:hover {
          border-color: var(--color-accent);
          background: var(--color-accent-soft);
          transform: var(--motion-hover-translate-y-sm);
        }

        .workflow-tab--active {
          border-color: var(--color-accent);
          background: var(--color-accent-soft);
          box-shadow: 0 0 0 3px var(--color-accent-glow), var(--shadow-sm);
        }
      `}</style>
    </div>
  );
}
