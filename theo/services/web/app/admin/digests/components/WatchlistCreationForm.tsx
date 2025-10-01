type WatchlistCreationFormProps = {
  name: string;
  cadence: string;
  deliveryChannels: string;
  topics: string;
  keywords: string;
  authors: string;
  osis: string;
  onNameChange: (value: string) => void;
  onCadenceChange: (value: string) => void;
  onDeliveryChannelsChange: (value: string) => void;
  onTopicsChange: (value: string) => void;
  onKeywordsChange: (value: string) => void;
  onAuthorsChange: (value: string) => void;
  onOsisChange: (value: string) => void;
  onSubmit: () => void;
  isCreating: boolean;
  error: string | null;
};

export default function WatchlistCreationForm({
  name,
  cadence,
  deliveryChannels,
  topics,
  keywords,
  authors,
  osis,
  onNameChange,
  onCadenceChange,
  onDeliveryChannelsChange,
  onTopicsChange,
  onKeywordsChange,
  onAuthorsChange,
  onOsisChange,
  onSubmit,
  isCreating,
  error,
}: WatchlistCreationFormProps): JSX.Element {
  return (
    <form
      className="stack"
      style={{ gap: "0.75rem", border: "1px solid #e2e8f0", padding: "1rem", borderRadius: "0.75rem" }}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <h3>Create watchlist</h3>
      <label>
        Name
        <input value={name} onChange={(event) => onNameChange(event.target.value)} required />
      </label>
      <label>
        Cadence
        <select value={cadence} onChange={(event) => onCadenceChange(event.target.value)}>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
      </label>
      <label>
        Delivery channels (comma separated)
        <input
          value={deliveryChannels}
          onChange={(event) => onDeliveryChannelsChange(event.target.value)}
          placeholder="in_app, email"
        />
      </label>
      <label>
        Topics (comma separated)
        <input value={topics} onChange={(event) => onTopicsChange(event.target.value)} />
      </label>
      <label>
        Keywords (comma separated)
        <input value={keywords} onChange={(event) => onKeywordsChange(event.target.value)} />
      </label>
      <label>
        Authors (comma separated)
        <input value={authors} onChange={(event) => onAuthorsChange(event.target.value)} />
      </label>
      <label>
        OSIS references (comma separated)
        <input value={osis} onChange={(event) => onOsisChange(event.target.value)} />
      </label>
      {error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : null}
      <button type="submit" className="button" disabled={isCreating}>
        {isCreating ? "Creating…" : "Create watchlist"}
      </button>
    </form>
  );
}
