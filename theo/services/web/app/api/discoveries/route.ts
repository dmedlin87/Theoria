import { NextResponse } from "next/server";

// This is a placeholder - will be replaced with actual backend API call
export async function GET() {
  try {
    // TODO: Call the actual FastAPI backend endpoint
    // const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
    // const response = await fetch(`${backendUrl}/api/discoveries`, {
    //   headers: {
    //     "Authorization": `Bearer ${process.env.THEO_SEARCH_API_KEY}`,
    //   },
    // });
    // const data = await response.json();
    
    // For now, return mock data for frontend testing
    const mockDiscoveries = [
      {
        id: "disc-1",
        type: "pattern",
        title: "Covenant Theology Cluster Detected",
        description: "Found 8 documents discussing covenant theology with shared thematic emphasis on the Abrahamic covenant and its fulfillment in Christ.",
        confidence: 0.87,
        relevanceScore: 0.92,
        viewed: false,
        createdAt: new Date().toISOString(),
        metadata: {
          relatedDocuments: ["doc-1", "doc-2", "doc-3"],
          relatedVerses: ["Gen.15.1", "Gen.17.1", "Gal.3.16"],
          relatedTopics: ["covenant theology", "abrahamic covenant"],
          patternData: {
            clusterSize: 8,
            sharedThemes: ["covenant", "promise", "fulfillment", "christology"],
            keyVerses: ["Gen.15.1", "Gen.17.1", "Gal.3.16", "Heb.8.6"],
          },
        },
      },
      {
        id: "disc-2",
        type: "contradiction",
        title: "Conflicting Views on Justification",
        description: "Two sources present different interpretations of justification by faith - one emphasizing imputed righteousness, the other emphasizing transformative grace.",
        confidence: 0.73,
        relevanceScore: 0.85,
        viewed: false,
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        metadata: {
          relatedDocuments: ["doc-4", "doc-5"],
          relatedVerses: ["Rom.3.23", "Rom.5.1", "Eph.2.8-9"],
          relatedTopics: ["justification", "faith", "righteousness"],
          contradictionData: {
            source1: "Reformed Commentary on Romans",
            source2: "Eastern Orthodox Perspective",
            contradictionType: "doctrinal",
            severity: "moderate",
          },
        },
      },
      {
        id: "disc-3",
        type: "gap",
        title: "Limited Coverage of Pneumatology",
        description: "Your corpus has extensive soteriology coverage (50+ documents) but only 3 documents on pneumatology. Consider adding resources on the Holy Spirit.",
        confidence: 0.95,
        relevanceScore: 0.78,
        viewed: true,
        createdAt: new Date(Date.now() - 172800000).toISOString(),
        metadata: {
          relatedTopics: ["pneumatology", "holy spirit", "trinity"],
          gapData: {
            missingTopic: "Pneumatology",
            relatedQueries: ["holy spirit", "third person of trinity", "gifts of the spirit"],
          },
        },
      },
      {
        id: "disc-4",
        type: "connection",
        title: "Isaiah 53 Referenced Across New Testament",
        description: "Discovered strong thematic connections between Isaiah 53 and 12 New Testament passages discussing the suffering servant and atonement.",
        confidence: 0.91,
        relevanceScore: 0.89,
        viewed: false,
        createdAt: new Date(Date.now() - 3600000).toISOString(),
        metadata: {
          relatedVerses: ["Isa.53.5", "Matt.8.17", "Acts.8.32", "1Pet.2.24"],
          relatedTopics: ["suffering servant", "atonement", "prophecy fulfillment"],
          connectionData: {
            nodeA: "Isa.53",
            nodeB: "1Pet.2",
            connectionType: "verse_reference",
            strength: 0.91,
          },
        },
      },
      {
        id: "disc-5",
        type: "trend",
        title: "Increased Focus on Eschatology",
        description: "Your research activity shows 340% increase in eschatology-related queries over the past 30 days compared to the previous period.",
        confidence: 0.82,
        relevanceScore: 0.74,
        viewed: false,
        createdAt: new Date(Date.now() - 7200000).toISOString(),
        metadata: {
          relatedTopics: ["eschatology", "end times", "second coming"],
          trendData: {
            metric: "eschatology queries",
            change: 340,
            timeframe: "last 30 days",
          },
        },
      },
      {
        id: "disc-6",
        type: "anomaly",
        title: "Unusual Citation Pattern in Recent Upload",
        description: "Your latest sermon transcript cites Acts more frequently than the Gospels, which is unusual compared to your historical pattern.",
        confidence: 0.68,
        relevanceScore: 0.71,
        viewed: true,
        createdAt: new Date(Date.now() - 259200000).toISOString(),
        metadata: {
          relatedDocuments: ["doc-sermon-123"],
          relatedTopics: ["citation analysis", "preaching patterns"],
          anomalyData: {
            expectedValue: "Gospels > Acts",
            actualValue: "Acts > Gospels",
            deviationScore: 0.68,
          },
        },
      },
    ];

    return NextResponse.json({
      discoveries: mockDiscoveries,
      stats: {
        total: mockDiscoveries.length,
        unviewed: mockDiscoveries.filter((d) => !d.viewed).length,
        byType: {
          pattern: mockDiscoveries.filter((d) => d.type === "pattern").length,
          contradiction: mockDiscoveries.filter((d) => d.type === "contradiction").length,
          gap: mockDiscoveries.filter((d) => d.type === "gap").length,
          connection: mockDiscoveries.filter((d) => d.type === "connection").length,
          trend: mockDiscoveries.filter((d) => d.type === "trend").length,
          anomaly: mockDiscoveries.filter((d) => d.type === "anomaly").length,
        },
        averageConfidence: mockDiscoveries.reduce((sum, d) => sum + d.confidence, 0) / mockDiscoveries.length,
      },
    });
  } catch (error) {
    console.error("Error fetching discoveries:", error);
    return NextResponse.json(
      { error: "Failed to fetch discoveries" },
      { status: 500 }
    );
  }
}
