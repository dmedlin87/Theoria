"use client";

interface SearchFiltersProps {
  query: string;
  osis: string;
  collection: string;
  author: string;
  sourceType: string;
  theologicalTradition: string;
  topicDomain: string;
  onQueryChange: (value: string) => void;
  onOsisChange: (value: string) => void;
  onCollectionChange: (value: string) => void;
  onAuthorChange: (value: string) => void;
  onSourceTypeChange: (value: string) => void;
  onTheologicalTraditionChange: (value: string) => void;
  onTopicDomainChange: (value: string) => void;
  onReset?: () => void;
}

const SOURCE_OPTIONS = [
  { label: "Any source", value: "" },
  { label: "PDF", value: "pdf" },
  { label: "Markdown", value: "markdown" },
  { label: "YouTube", value: "youtube" },
  { label: "Transcript", value: "transcript" },
];

const TRADITION_OPTIONS = [
  { label: "Any tradition", value: "" },
  { label: "Anglican Communion", value: "anglican" },
  { label: "Baptist", value: "baptist" },
  { label: "Roman Catholic", value: "catholic" },
  { label: "Eastern Orthodox", value: "orthodox" },
  { label: "Reformed", value: "reformed" },
  { label: "Wesleyan/Methodist", value: "wesleyan" },
];

const DOMAIN_OPTIONS = [
  { label: "Any topic", value: "" },
  { label: "Christology", value: "christology" },
  { label: "Soteriology", value: "soteriology" },
  { label: "Ecclesiology", value: "ecclesiology" },
  { label: "Sacramental Theology", value: "sacramental" },
  { label: "Biblical Theology", value: "biblical-theology" },
  { label: "Christian Ethics", value: "ethics" },
];

export default function SearchFilters({
  query,
  osis,
  collection,
  author,
  sourceType,
  theologicalTradition,
  topicDomain,
  onQueryChange,
  onOsisChange,
  onCollectionChange,
  onAuthorChange,
  onSourceTypeChange,
  onTheologicalTraditionChange,
  onTopicDomainChange,
  onReset,
}: SearchFiltersProps): JSX.Element {
  return (
    <div className="card">
      <div className="panel__header">
        <h2 className="panel__title">Search filters</h2>
        {onReset && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onReset}>
            Clear all
          </button>
        )}
      </div>
      
      <div className="stack-md">
        <div className="form-field">
          <label htmlFor="search-query" className="form-label">
            Search Query
          </label>
          <input
            id="search-query"
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Enter keywords..."
            className="form-input"
          />
        </div>

        <div className="form-field">
          <label htmlFor="search-osis" className="form-label">
            OSIS Reference
          </label>
          <input
            id="search-osis"
            type="text"
            value={osis}
            onChange={(e) => onOsisChange(e.target.value)}
            placeholder="e.g., John.1.1"
            className="form-input"
          />
        </div>

        <div className="form-field">
          <label htmlFor="search-collection" className="form-label">
            Collection
          </label>
          <input
            id="search-collection"
            type="text"
            value={collection}
            onChange={(e) => onCollectionChange(e.target.value)}
            placeholder="Collection name"
            className="form-input"
          />
        </div>

        <div className="form-field">
          <label htmlFor="search-author" className="form-label">
            Author
          </label>
          <input
            id="search-author"
            type="text"
            value={author}
            onChange={(e) => onAuthorChange(e.target.value)}
            placeholder="Author name"
            className="form-input"
          />
        </div>

        <div className="form-field">
          <label htmlFor="search-source-type" className="form-label">
            Source Type
          </label>
          <select
            id="search-source-type"
            value={sourceType}
            onChange={(e) => onSourceTypeChange(e.target.value)}
            className="form-select"
          >
            {SOURCE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="search-tradition" className="form-label">
            Theological Tradition
          </label>
          <select
            id="search-tradition"
            value={theologicalTradition}
            onChange={(e) => onTheologicalTraditionChange(e.target.value)}
            className="form-select"
          >
            {TRADITION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="search-domain" className="form-label">
            Topic Domain
          </label>
          <select
            id="search-domain"
            value={topicDomain}
            onChange={(e) => onTopicDomainChange(e.target.value)}
            className="form-select"
          >
            {DOMAIN_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
