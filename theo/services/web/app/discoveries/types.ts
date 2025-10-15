export type DiscoveryType = 
  | "pattern" 
  | "contradiction" 
  | "gap" 
  | "connection"
  | "trend"
  | "anomaly";

export interface Discovery {
  id: string;
  type: DiscoveryType;
  title: string;
  description: string;
  confidence: number; // 0-1
  relevanceScore: number; // 0-1
  viewed: boolean;
  createdAt: string;
  userReaction?: "helpful" | "not_helpful" | "dismiss";
  metadata: DiscoveryMetadata;
}

export interface DiscoveryMetadata {
  // Related entities
  relatedDocuments?: string[];
  relatedVerses?: string[];
  relatedTopics?: string[];
  
  // Type-specific data
  patternData?: {
    clusterSize: number;
    sharedThemes: string[];
    keyVerses: string[];
  };
  
  contradictionData?: {
    source1: string;
    source2: string;
    contradictionType: "doctrinal" | "interpretation" | "application";
    severity: "minor" | "moderate" | "major";
  };
  
  gapData?: {
    missingTopic: string;
    suggestedSources?: string[];
    relatedQueries: string[];
  };
  
  connectionData?: {
    nodeA: string;
    nodeB: string;
    connectionType: "verse_reference" | "thematic" | "authorial" | "linguistic";
    strength: number;
  };
  
  trendData?: {
    metric: string;
    change: number; // percentage
    timeframe: string;
  };
  
  anomalyData?: {
    expectedValue: string;
    actualValue: string;
    deviationScore: number;
  };
}

export interface DiscoveryStats {
  total: number;
  unviewed: number;
  byType: Record<DiscoveryType, number>;
  averageConfidence: number;
}
