"use client";

import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { useEffect, useMemo, useState } from "react";

import { buildPassageLink, formatAnchor } from "../../lib/api";
import type {
  VerseGraphEdge,
  VerseGraphNode,
  VerseGraphResponse,
} from "./graphTypes";

const SVG_WIDTH = 760;
const SVG_HEIGHT = 520;

interface LayoutNode extends SimulationNodeDatum {
  id: string;
  raw: VerseGraphNode;
}

interface LayoutLink extends SimulationLinkDatum<LayoutNode> {
  raw: VerseGraphEdge;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function asStringArray(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const coerced = value
    .map((entry) => (typeof entry === "string" ? entry : String(entry)))
    .filter((entry) => entry);
  return coerced.length > 0 ? coerced : null;
}

function edgeColour(edge: VerseGraphEdge): string {
  switch (edge.kind) {
    case "contradiction":
      return "#ef4444";
    case "harmony":
      return "#22c55e";
    case "commentary":
      return "#fb923c";
    default:
      return "#60a5fa";
  }
}

function nodeFill(node: VerseGraphNode): string {
  switch (node.kind) {
    case "verse":
      return "#1d4ed8";
    case "commentary":
      return "#fb923c";
    default:
      return "#10b981";
  }
}

function nodeRadius(node: VerseGraphNode): number {
  switch (node.kind) {
    case "verse":
      return 36;
    case "commentary":
      return 24;
    default:
      return 28;
  }
}

function titleCase(value: string): string {
  if (!value) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function upperLabel(value: string): string {
  return value.toUpperCase();
}

function getNodeId(ref: string | number | LayoutNode): string {
  if (typeof ref === "string") return ref;
  if (typeof ref === "number") return String(ref);
  return ref.id;
}

interface VerseGraphSectionProps {
  graph: VerseGraphResponse | null;
}

export default function VerseGraphSection({ graph }: VerseGraphSectionProps) {
  const [layout, setLayout] = useState<{ nodes: LayoutNode[]; links: LayoutLink[] } | null>(
    null,
  );
  const [selectedPerspectives, setSelectedPerspectives] = useState<string[]>([]);
  const [selectedSourceTypes, setSelectedSourceTypes] = useState<string[]>([]);

  useEffect(() => {
    if (!graph) {
      setSelectedPerspectives([]);
      setSelectedSourceTypes([]);
      setLayout(null);
      return;
    }
    setSelectedPerspectives(graph.filters.perspectives.slice());
    setSelectedSourceTypes(graph.filters.source_types.slice());

    const nodes: LayoutNode[] = graph.nodes.map((node) => ({
      id: node.id,
      raw: node,
      x: SVG_WIDTH / 2 + (Math.random() - 0.5) * 40,
      y: SVG_HEIGHT / 2 + (Math.random() - 0.5) * 40,
    }));
    const links: LayoutLink[] = graph.edges.map((edge) => ({
      raw: edge,
      source: edge.source,
      target: edge.target,
    })) as unknown as LayoutLink[];

    if (nodes.length === 0) {
      setLayout({ nodes: [], links: [] });
      return;
    }

    const simulation = forceSimulation<LayoutNode>(nodes)
      .force(
        "link",
        forceLink<LayoutNode, LayoutLink>(links)
          .id((node) => node.id)
          .distance((link) => (link.raw.kind === "mention" ? 140 : 180))
          .strength(0.45),
      )
      .force("charge", forceManyBody().strength(-220))
      .force("center", forceCenter(SVG_WIDTH / 2, SVG_HEIGHT / 2))
      .force(
        "collision",
        forceCollide<LayoutNode>().radius((node) => nodeRadius(node.raw) + 12),
      );

    simulation.stop();
    for (let index = 0; index < 320; index += 1) {
      simulation.tick();
    }

    setLayout({ nodes, links });

    return () => {
      simulation.stop();
    };
  }, [graph]);

  const perspectiveSet = useMemo(
    () => new Set(selectedPerspectives),
    [selectedPerspectives],
  );
  const sourceTypeSet = useMemo(
    () => new Set(selectedSourceTypes),
    [selectedSourceTypes],
  );

  const perspectiveFilterActive = useMemo(() => {
    if (!graph) {
      return false;
    }
    const total = graph.filters.perspectives.length;
    return total > 0 && selectedPerspectives.length < total;
  }, [graph, selectedPerspectives]);

  const sourceTypeFilterActive = useMemo(() => {
    if (!graph) {
      return false;
    }
    const total = graph.filters.source_types.length;
    return total > 0 && selectedSourceTypes.length < total;
  }, [graph, selectedSourceTypes]);

  const visibleLinks = useMemo(() => {
    if (!layout) {
      return [] as LayoutLink[];
    }
    return layout.links.filter((link) => {
      const edge = link.raw;
      if (edge.kind === "mention") {
        if (sourceTypeFilterActive) {
          if (!edge.source_type || !sourceTypeSet.has(edge.source_type)) {
            return false;
          }
        }
        return true;
      }
      if (perspectiveFilterActive) {
        if (!edge.perspective || !perspectiveSet.has(edge.perspective)) {
          return false;
        }
      }
      return true;
    });
  }, [layout, perspectiveFilterActive, perspectiveSet, sourceTypeFilterActive, sourceTypeSet]);

  const baseNodeId = graph ? `verse:${graph.osis}` : null;

  const visibleNodeIds = useMemo(() => {
    const ids = new Set<string>();
    if (baseNodeId) {
      ids.add(baseNodeId);
    }
    for (const link of visibleLinks) {
      ids.add(getNodeId(link.source));
      ids.add(getNodeId(link.target));
    }
    return ids;
  }, [baseNodeId, visibleLinks]);

  const visibleNodes = useMemo(() => {
    if (!layout) {
      return [] as LayoutNode[];
    }
    return layout.nodes.filter((node) => visibleNodeIds.has(node.id));
  }, [layout, visibleNodeIds]);

  const togglePerspective = (value: string) => {
    setSelectedPerspectives((prev) =>
      prev.includes(value)
        ? prev.filter((item) => item !== value)
        : [...prev, value],
    );
  };

  const toggleSourceType = (value: string) => {
    setSelectedSourceTypes((prev) =>
      prev.includes(value)
        ? prev.filter((item) => item !== value)
        : [...prev, value],
    );
  };

  if (!graph) {
    return (
      <section aria-labelledby="verse-graph-heading" style={{ margin: "2rem 0" }}>
        <h3 id="verse-graph-heading" style={{ marginBottom: "0.5rem" }}>
          Verse graph
        </h3>
        <p style={{ margin: 0 }}>Graph data is not available for this verse.</p>
      </section>
    );
  }

  const visibleRelationshipCount = visibleLinks.length;
  const totalRelationships = graph.edges.length;

  return (
    <section aria-labelledby="verse-graph-heading" style={{ margin: "2rem 0" }}>
      <h3 id="verse-graph-heading" style={{ marginBottom: "0.5rem" }}>
        Relationship graph
      </h3>
      <p
        data-testid="verse-graph-summary"
        style={{ margin: "0 0 1rem", color: "var(--muted-foreground, #4b5563)" }}
      >
        Showing {visibleRelationshipCount} of {totalRelationships} relationships.
      </p>
      <div
        style={{
          display: "grid",
          gap: "1.5rem",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 2fr)",
          alignItems: "start",
        }}
      >
        <div style={{ display: "grid", gap: "1rem" }}>
          {graph.filters.perspectives.length > 0 ? (
            <fieldset style={{ border: "1px solid #e5e7eb", borderRadius: "0.5rem", padding: "1rem" }}>
              <legend style={{ fontWeight: 600 }}>Perspectives</legend>
              {graph.filters.perspectives.map((perspective) => (
                <label key={perspective} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={selectedPerspectives.includes(perspective)}
                    onChange={() => togglePerspective(perspective)}
                  />
                  {titleCase(perspective)}
                </label>
              ))}
            </fieldset>
          ) : null}
          {graph.filters.source_types.length > 0 ? (
            <fieldset style={{ border: "1px solid #e5e7eb", borderRadius: "0.5rem", padding: "1rem" }}>
              <legend style={{ fontWeight: 600 }}>Source types</legend>
              {graph.filters.source_types.map((sourceType) => (
                <label key={sourceType} style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={selectedSourceTypes.includes(sourceType)}
                    onChange={() => toggleSourceType(sourceType)}
                  />
                  {upperLabel(sourceType)}
                </label>
              ))}
            </fieldset>
          ) : null}
        </div>
        <div
          data-testid="verse-graph"
          style={{
            background: "#fff",
            borderRadius: "0.75rem",
            border: "1px solid #e2e8f0",
            padding: "1rem",
            overflow: "hidden",
          }}
        >
          {visibleLinks.length === 0 && visibleNodes.length <= 1 ? (
            <p style={{ margin: 0 }}>
              We couldn&apos;t find related mentions or research seeds for these filters yet.
            </p>
          ) : (
            <svg
              role="img"
              aria-label={`Graph showing relationships for ${graph.osis}`}
              width={SVG_WIDTH}
              height={SVG_HEIGHT}
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
            >
              <defs>
                <filter id="node-shadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="#0f172a" floodOpacity="0.15" />
                </filter>
              </defs>
              {visibleLinks.map((link) => {
                const source = typeof link.source === "string" ? layout?.nodes.find((node) => node.id === link.source) : (link.source as LayoutNode);
                const target = typeof link.target === "string" ? layout?.nodes.find((node) => node.id === link.target) : (link.target as LayoutNode);
                const x1 = source?.x ?? SVG_WIDTH / 2;
                const y1 = source?.y ?? SVG_HEIGHT / 2;
                const x2 = target?.x ?? SVG_WIDTH / 2;
                const y2 = target?.y ?? SVG_HEIGHT / 2;
                return (
                  <line
                    key={link.raw.id}
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={edgeColour(link.raw)}
                    strokeWidth={link.raw.kind === "mention" ? 2 : 3}
                    strokeOpacity={0.85}
                  >
                    {link.raw.summary ? <title>{link.raw.summary}</title> : null}
                  </line>
                );
              })}
              {visibleNodes.map((node) => {
                const x = node.x ?? SVG_WIDTH / 2;
                const y = node.y ?? SVG_HEIGHT / 2;
                const radius = nodeRadius(node.raw);
                const data = asRecord(node.raw.data);
                const documentId = data ? asString(data["document_id"]) : null;
                const passageId = data ? asString(data["passage_id"]) : null;
                const pageNo = data ? asNumber(data["page_no"]) : null;
                const tStart = data ? asNumber(data["t_start"]) : null;
                const tEnd = data ? asNumber(data["t_end"]) : null;
                const documentTitle = data ? asString(data["document_title"]) : null;
                const excerpt = data ? asString(data["excerpt"]) : null;
                const authors = data ? asStringArray(data["authors"]) : null;

                const mentionHref =
                  node.raw.kind === "mention" && documentId && passageId
                    ? buildPassageLink(documentId, passageId, {
                        pageNo: pageNo ?? null,
                        tStart: tStart ?? null,
                      })
                    : null;

                const anchor =
                  node.raw.kind === "mention"
                    ? formatAnchor({
                        page_no: pageNo ?? null,
                        t_start: tStart ?? null,
                        t_end: tEnd ?? null,
                      })
                    : null;

                const linkLabel =
                  node.raw.kind === "mention"
                    ? `${documentTitle || "Open mention"}${anchor ? ` – ${anchor}` : ""}`
                    : node.raw.label;

                const circle = (
                  <circle
                    cx={x}
                    cy={y}
                    r={radius}
                    fill={nodeFill(node.raw)}
                    stroke="#0f172a"
                    strokeOpacity={0.2}
                    filter="url(#node-shadow)"
                  >
                    <title>
                      {node.raw.kind === "mention"
                        ? `${node.raw.label}${anchor ? ` (${anchor})` : ""}`
                        : excerpt || node.raw.label}
                    </title>
                  </circle>
                );

                return (
                  <g key={node.id}>
                    {mentionHref ? (
                      <a
                        href={mentionHref}
                        aria-label={`Open ${linkLabel}`}
                        data-testid={`graph-node-link-${node.raw.id}`}
                      >
                        {circle}
                      </a>
                    ) : (
                      circle
                    )}
                    <text
                      x={x}
                      y={y - radius - 8}
                      textAnchor="middle"
                      fontSize={12}
                      fill="#0f172a"
                    >
                      {node.raw.label}
                    </text>
                    {node.raw.kind === "commentary" && excerpt ? (
                      <text
                        x={x}
                        y={y + radius + 14}
                        textAnchor="middle"
                        fontSize={11}
                        fill="#334155"
                      >
                        {excerpt.length > 40 ? `${excerpt.slice(0, 37)}…` : excerpt}
                      </text>
                    ) : null}
                    {node.raw.kind === "mention" && authors && authors.length > 0 ? (
                      <text
                        x={x}
                        y={y + radius + 14}
                        textAnchor="middle"
                        fontSize={11}
                        fill="#334155"
                      >
                        {authors.join(", ")}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </svg>
          )}
        </div>
      </div>
    </section>
  );
}
