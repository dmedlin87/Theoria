export function isCaseBuilderEnabled(): boolean {
  const raw =
    process.env.NEXT_PUBLIC_CASE_BUILDER_ENABLED ??
    process.env.CASE_BUILDER_ENABLED ??
    "false";
  if (typeof raw !== "string") {
    return false;
  }
  const normalised = raw.trim().toLowerCase();
  return normalised === "1" || normalised === "true";
}

export default isCaseBuilderEnabled;
