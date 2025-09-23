import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Theo Engine",
  description: "Research engine for theology",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header>
          <h1>Theo Engine</h1>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
