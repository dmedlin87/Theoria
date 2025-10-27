import HypothesesDashboardClient from "./HypothesesDashboardClient";
import { DEFAULT_FILTERS, fetchHypotheses } from "./client";

export const metadata = {
  title: "Hypotheses • Theo Research",
};

export default async function HypothesesPage() {
  const initialData = await fetchHypotheses(DEFAULT_FILTERS, { cache: "no-store" });
  return (
    <HypothesesDashboardClient
      initialHypotheses={initialData.hypotheses}
      initialTotal={initialData.total}
      initialFilters={DEFAULT_FILTERS}
    />
  );
}
