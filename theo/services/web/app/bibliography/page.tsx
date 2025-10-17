import type { Metadata } from "next";
import BibliographyBuilder from "./BibliographyBuilder";

export const metadata: Metadata = {
  title: "Bibliography Builder • Theoria",
  description: "Build and export citations in multiple formats",
};

export default function BibliographyPage() {
  return <BibliographyBuilder />;
}
