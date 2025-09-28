type WorkflowOption = {
  id: string;
  label: string;
  description: string;
};

type WorkflowSelectorProps = {
  options: WorkflowOption[];
  selected: string;
  onSelect: (workflow: string) => void;
};

export default function WorkflowSelector({ options, selected, onSelect }: WorkflowSelectorProps): JSX.Element {
  return (
    <div style={{ display: "flex", gap: "0.75rem", margin: "1.5rem 0", flexWrap: "wrap" }}>
      {options.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item.id)}
          className={`workflow-button${selected === item.id ? " is-active" : ""}`}
          aria-pressed={selected === item.id}
        >
          <span className="workflow-header">
            <strong>{item.label}</strong>
            {selected === item.id && (
              <span aria-hidden="true" className="workflow-indicator">
                Selected
              </span>
            )}
          </span>
          <span className="workflow-description">{item.description}</span>
          <span className="sr-only">
            {selected === item.id
              ? `${item.label} workflow currently selected.`
              : `Activate the ${item.label} workflow.`}
          </span>
        </button>
      ))}
    </div>
  );
}
