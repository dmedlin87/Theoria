export function getApiBaseUrl(): string {
  if (typeof process !== "undefined") {
    return (
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      process.env.API_BASE_URL ||
      "http://127.0.0.1:8000"
    );
  }
  return "http://127.0.0.1:8000";
}

export function getCitationManagerEndpoint(): string | null {
  if (typeof process !== "undefined") {
    return process.env.NEXT_PUBLIC_CITATION_MANAGER_URL || null;
  }
  return null;
}

export function buildPassageLink(
  documentId: string,
  passageId: string,
  {
    pageNo,
    tStart,
  }: {
    pageNo?: number | null;
    tStart?: number | null;
  }
): string {
  const params = new URLSearchParams();
  if (typeof pageNo === "number") {
    params.set("page", String(pageNo));
  }
  if (typeof tStart === "number") {
    params.set("t", Math.floor(tStart).toString());
  }
  const query = params.toString();
  const basePath = `/doc/${documentId}`;
  const hash = `#passage-${passageId}`;
  return query ? `${basePath}?${query}${hash}` : `${basePath}${hash}`;
}

export function formatAnchor(
  passage: { page_no?: number | null; t_start?: number | null; t_end?: number | null }
): string {
  const anchors: string[] = [];
  if (typeof passage.page_no === "number") {
    anchors.push(`Page ${passage.page_no}`);
  }
  if (typeof passage.t_start === "number") {
    const end = typeof passage.t_end === "number" ? passage.t_end : undefined;
    anchors.push(
      end && end > passage.t_start
        ? `Timestamp ${passage.t_start.toFixed(1)}s – ${end.toFixed(1)}s`
        : `Timestamp ${passage.t_start.toFixed(1)}s`
    );
  }
  return anchors.join(" · ");
}
