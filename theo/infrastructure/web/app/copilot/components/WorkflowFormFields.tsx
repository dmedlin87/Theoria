import styles from "./WorkflowFormFields.module.css";
import type { ExportPreset, ExportPresetId, WorkflowId } from "./types";
import type {
  CollaborationFormState,
  ComparativeFormState,
  CurationFormState,
  DevotionalFormState,
  ExportFormState,
  MultimediaFormState,
  SermonFormState,
  VerseFormState,
} from "./workflow-hooks";

type WorkflowFormFieldsProps = {
  workflow: WorkflowId;
  exportPresets: ExportPreset[];
  verse: { form: VerseFormState; onChange: (updates: Partial<VerseFormState>) => void };
  sermon: { form: SermonFormState; onChange: (updates: Partial<SermonFormState>) => void };
  comparative: { form: ComparativeFormState; onChange: (updates: Partial<ComparativeFormState>) => void };
  multimedia: { form: MultimediaFormState; onChange: (updates: Partial<MultimediaFormState>) => void };
  devotional: { form: DevotionalFormState; onChange: (updates: Partial<DevotionalFormState>) => void };
  collaboration: { form: CollaborationFormState; onChange: (updates: Partial<CollaborationFormState>) => void };
  curation: { form: CurationFormState; onChange: (updates: Partial<CurationFormState>) => void };
  exportPreset: { form: ExportFormState; onChange: (updates: Partial<ExportFormState>) => void };
  onVerseCommand?: (value: string) => boolean;
};

export default function WorkflowFormFields({
  workflow,
  exportPresets,
  verse,
  sermon,
  comparative,
  multimedia,
  devotional,
  collaboration,
  curation,
  exportPreset,
  onVerseCommand,
}: WorkflowFormFieldsProps): JSX.Element | null {
  switch (workflow) {
    case "verse":
      return (
        <>
          <label>
            Passage
            <input
              type="text"
              value={verse.form.passage}
              onChange={(event) => verse.onChange({ passage: event.target.value })}
              placeholder="Mark 16:9–20"
              required={!verse.form.useAdvanced}
              className={styles.fullWidthInput}
            />
          </label>
          {!verse.form.useAdvanced && (
            <p className={styles.helperText}>
              Describe a passage naturally, such as "Mark 16:9–20" or "John 1:1-5". We will resolve the exact
              reference for you.
            </p>
          )}
          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={verse.form.useAdvanced}
              onChange={(event) => verse.onChange({ useAdvanced: event.target.checked })}
            />
            Advanced mode (use OSIS)
          </label>
          {verse.form.useAdvanced && (
            <>
              <label>
                OSIS reference
                <input
                  type="text"
                  value={verse.form.osis}
                  onChange={(event) => verse.onChange({ osis: event.target.value })}
                  placeholder="John.1.1-5"
                  required
                  className={styles.fullWidthInput}
                />
              </label>
            </>
          )}
          <label>
            Question (optional)
            <input
              type="text"
              value={verse.form.question}
              onChange={(event) => verse.onChange({ question: event.target.value })}
              onKeyDown={(event) => {
                if (!onVerseCommand) {
                  return;
                }
                if (event.key === "Enter") {
                  const handled = onVerseCommand(event.currentTarget.value);
                  if (handled) {
                    event.preventDefault();
                    event.stopPropagation();
                  }
                }
              }}
              placeholder="What themes emerge in the Beatitudes?"
              className={styles.fullWidthInput}
            />
          </label>
        </>
      );
    case "sermon":
      return (
        <>
          <label>
            Topic
            <input
              type="text"
              value={sermon.form.topic}
              onChange={(event) => sermon.onChange({ topic: event.target.value })}
              placeholder="Grace and forgiveness"
              required
              className={styles.fullWidthInput}
            />
          </label>
          <label>
            OSIS anchor (optional)
            <input
              type="text"
              value={sermon.form.osis}
              onChange={(event) => sermon.onChange({ osis: event.target.value })}
              placeholder="Luke.15"
              className={styles.fullWidthInput}
            />
          </label>
        </>
      );
    case "comparative":
      return (
        <>
          <label>
            OSIS reference
            <input
              type="text"
              value={comparative.form.osis}
              onChange={(event) => comparative.onChange({ osis: event.target.value })}
              placeholder="John.1.1"
              required
              className={styles.fullWidthInput}
            />
          </label>
          <label>
            Participants (comma separated)
            <input
              type="text"
              value={comparative.form.participants}
              onChange={(event) => comparative.onChange({ participants: event.target.value })}
              placeholder="Augustine, Luther, Calvin"
              required
              className={styles.fullWidthInput}
            />
          </label>
        </>
      );
    case "multimedia":
      return (
        <label>
          Collection (optional)
          <input
            type="text"
            value={multimedia.form.collection}
            onChange={(event) => multimedia.onChange({ collection: event.target.value })}
            placeholder="Gospels"
            className={styles.fullWidthInput}
          />
        </label>
      );
    case "devotional":
      return (
        <>
          <label>
            OSIS reference
            <input
              type="text"
              value={devotional.form.osis}
              onChange={(event) => devotional.onChange({ osis: event.target.value })}
              placeholder="John.1.1-5"
              required
              className={styles.fullWidthInput}
            />
          </label>
          <label>
            Focus theme
            <input
              type="text"
              value={devotional.form.focus}
              onChange={(event) => devotional.onChange({ focus: event.target.value })}
              placeholder="God's Word in creation"
              required
              className={styles.fullWidthInput}
            />
          </label>
        </>
      );
    case "collaboration":
      return (
        <>
          <label>
            Thread identifier
            <input
              type="text"
              value={collaboration.form.thread}
              onChange={(event) => collaboration.onChange({ thread: event.target.value })}
              placeholder="forum-thread-42"
              required
              className={styles.fullWidthInput}
            />
          </label>
          <label>
            OSIS reference
            <input
              type="text"
              value={collaboration.form.osis}
              onChange={(event) => collaboration.onChange({ osis: event.target.value })}
              placeholder="Romans.8.1-4"
              required
              className={styles.fullWidthInput}
            />
          </label>
          <label>
            Viewpoints (comma separated)
            <input
              type="text"
              value={collaboration.form.viewpoints}
              onChange={(event) => collaboration.onChange({ viewpoints: event.target.value })}
              placeholder="Logos Christology, Early Fathers, Reformers"
              required
              className={styles.fullWidthInput}
            />
          </label>
        </>
      );
    case "curation":
      return (
        <label>
          Since (ISO timestamp, optional)
          <input
            type="text"
            value={curation.form.since}
            onChange={(event) => curation.onChange({ since: event.target.value })}
            placeholder="2024-01-01T00:00:00"
            className={styles.fullWidthInput}
          />
        </label>
      );
    case "export":
      return (
        <>
          <label>
            Export preset
            <select
              value={exportPreset.form.preset}
              onChange={(event) =>
                exportPreset.onChange({ preset: event.target.value as ExportPresetId })
              }
              name="exportPreset"
              className={styles.fullWidthSelect}
            >
              {exportPresets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>
          {(() => {
            const preset = exportPresets.find((item) => item.id === exportPreset.form.preset);
            if (!preset) {
              return null;
            }
            if (preset.type === "sermon") {
              return (
                <>
                  <p className={styles.presetDescription}>{preset.description}</p>
                  <label>
                    Sermon topic
                    <input
                      type="text"
                      value={exportPreset.form.topic}
                      onChange={(event) => exportPreset.onChange({ topic: event.target.value })}
                      placeholder="Embodied hope"
                      required
                      className={styles.fullWidthInput}
                    />
                  </label>
                  <label>
                    OSIS anchor (optional)
                    <input
                      type="text"
                      value={exportPreset.form.osis}
                      onChange={(event) => exportPreset.onChange({ osis: event.target.value })}
                      placeholder="John.1.1"
                      className={styles.fullWidthInput}
                    />
                  </label>
                </>
              );
            }
            return (
              <>
                <p className={styles.presetDescription}>{preset.description}</p>
                <label>
                  Document identifier
                  <input
                    type="text"
                    value={exportPreset.form.documentId}
                    onChange={(event) => exportPreset.onChange({ documentId: event.target.value })}
                    placeholder="doc-123"
                    required
                    className={styles.fullWidthInput}
                  />
                </label>
              </>
            );
          })()}
        </>
      );
    default:
      return null;
  }
}
