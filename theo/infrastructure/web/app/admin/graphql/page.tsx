import { notFound } from "next/navigation";

import GraphQLExplorer from "./GraphQLExplorer";

export const metadata = {
  title: "GraphQL explorer",
};

function flagEnabled(value: string | undefined): boolean {
  return typeof value === "string" && value.trim().toLowerCase() === "true";
}

const adminEnabled = flagEnabled(process.env.NEXT_PUBLIC_ENABLE_ADMIN);
const explorerEnabled = flagEnabled(
  process.env.NEXT_PUBLIC_ENABLE_GRAPHQL_EXPLORER ??
    process.env.ENABLE_GRAPHQL_EXPLORER ??
    process.env.NEXT_PUBLIC_ENABLE_ADMIN_GRAPHQL ??
    process.env.ENABLE_ADMIN_GRAPHQL,
);

if (!adminEnabled || !explorerEnabled) {
  notFound();
}

export default function AdminGraphQLPage() {
  return <GraphQLExplorer />;
}
