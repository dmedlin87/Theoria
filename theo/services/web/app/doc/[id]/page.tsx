import { notFound } from "next/navigation";

import DocumentClient from "./DocumentClient";
import type { DocumentDetail } from "./types";
import { getApiBaseUrl } from "../../lib/api";

interface DocumentPageProps {
  params: Promise<{ id: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}

async function fetchDocument(id: string): Promise<DocumentDetail> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/documents/${id}`, { cache: "no-store" });
  if (response.status === 404) {
    notFound();
  }
  if (!response.ok) {
    throw new Error(`Failed to load document: ${response.statusText}`);
  }
  return (await response.json()) as DocumentDetail;
}

export default async function DocumentPage({ params }: DocumentPageProps) {
  const { id } = await params;
  const document = await fetchDocument(id);
  return <DocumentClient initialDocument={document} />;
}
