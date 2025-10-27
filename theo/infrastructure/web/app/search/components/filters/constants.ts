import { type SearchFilters } from "../../searchParams";

export const SOURCE_OPTIONS = [
  { label: "Any source", value: "" },
  { label: "PDF", value: "pdf" },
  { label: "Markdown", value: "markdown" },
  { label: "YouTube", value: "youtube" },
  { label: "Transcript", value: "transcript" },
] as const;

export const TRADITION_OPTIONS = [
  { label: "Any tradition", value: "" },
  { label: "Anglican Communion", value: "anglican" },
  { label: "Baptist", value: "baptist" },
  { label: "Roman Catholic", value: "catholic" },
  { label: "Eastern Orthodox", value: "orthodox" },
  { label: "Reformed", value: "reformed" },
  { label: "Wesleyan/Methodist", value: "wesleyan" },
] as const;

export const DOMAIN_OPTIONS = [
  { label: "Any topic", value: "" },
  { label: "Christology", value: "christology" },
  { label: "Soteriology", value: "soteriology" },
  { label: "Ecclesiology", value: "ecclesiology" },
  { label: "Sacramental Theology", value: "sacramental" },
  { label: "Biblical Theology", value: "biblical-theology" },
  { label: "Christian Ethics", value: "ethics" },
] as const;

export const COLLECTION_FACETS = [
  "Dead Sea Scrolls",
  "Nag Hammadi",
  "Church Fathers",
  "Second Temple",
] as const;

export const DATASET_FILTERS = [
  {
    label: "Dead Sea Scrolls",
    value: "dss",
    description: "Qumran fragments and related parallels",
  },
  {
    label: "Nag Hammadi Codices",
    value: "nag-hammadi",
    description: "Gnostic corpus for comparative study",
  },
] as const;

export const VARIANT_FILTERS = [
  { label: "Disputed readings", value: "disputed" },
  { label: "Harmonized expansions", value: "harmonized" },
  { label: "Orthographic shifts", value: "orthographic" },
] as const;

export const DATASET_LABELS = new Map(
  DATASET_FILTERS.map((option) => [option.value, option.label] as const),
);

export const VARIANT_LABELS = new Map(
  VARIANT_FILTERS.map((option) => [option.value, option.label] as const),
);

export const SOURCE_LABELS = new Map(
  SOURCE_OPTIONS.map((option) => [option.value, option.label] as const),
);

export const TRADITION_LABELS = new Map(
  TRADITION_OPTIONS.map((option) => [option.value, option.label] as const),
);

export const DOMAIN_LABELS = new Map(
  DOMAIN_OPTIONS.map((option) => [option.value, option.label] as const),
);

export const CUSTOM_PRESET_VALUE = "custom";

export type ModePreset = {
  value: string;
  label: string;
  description: string;
  filters?: Partial<SearchFilters>;
};

export const MODE_PRESETS: ModePreset[] = [
  {
    value: CUSTOM_PRESET_VALUE,
    label: "Manual configuration",
    description: "Start with an empty slate and tune filters yourself.",
  },
  {
    value: "scholar",
    label: "Scholarly exegesis",
    description: "Variants + disputed passages with manuscript-heavy sources.",
    filters: {
      includeVariants: true,
      includeDisputed: true,
      collectionFacets: ["Dead Sea Scrolls", "Church Fathers"],
      datasetFacets: ["dss"],
      variantFacets: ["disputed"],
      sourceType: "pdf",
    },
  },
  {
    value: "devotional",
    label: "Devotional overview",
    description: "Focus on canonical material and mainstream commentary.",
    filters: {
      includeVariants: false,
      includeDisputed: false,
      collectionFacets: ["Church Fathers"],
      datasetFacets: [],
      variantFacets: [],
      sourceType: "markdown",
    },
  },
  {
    value: "textual-critical",
    label: "Textual criticism",
    description: "Surface disputed readings and variant apparatus notes.",
    filters: {
      includeVariants: true,
      includeDisputed: true,
      collectionFacets: ["Dead Sea Scrolls", "Second Temple"],
      datasetFacets: ["dss"],
      variantFacets: ["disputed", "harmonized"],
      sourceType: "pdf",
    },
  },
];

export function getPresetLabel(value: string): string {
  const preset = MODE_PRESETS.find((item) => item.value === value);
  return preset ? preset.label : value;
}
