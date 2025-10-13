import styles from "./workflow-selector.module.css";
import "../../components/ui/tokens.module.css";

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
    <div className={styles.list}>
      {options.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onSelect(item.id)}
          className={
            selected === item.id
              ? `${styles.button} ${styles.buttonActive}`
              : styles.button
          }
          aria-pressed={selected === item.id}
        >
          <span className={styles.header}>
            <strong>{item.label}</strong>
            {selected === item.id && (
              <span aria-hidden="true" className={styles.indicator}>
                Selected
              </span>
            )}
          </span>
          <span className={styles.description}>{item.description}</span>
          <span className={styles.srOnly}>
            {selected === item.id
              ? `${item.label} workflow currently selected.`
              : `Activate the ${item.label} workflow.`}
          </span>
        </button>
      ))}
    </div>
  );
}
