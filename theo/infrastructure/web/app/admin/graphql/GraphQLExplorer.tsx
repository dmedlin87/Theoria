"use client";

import { useMemo } from "react";
import { GraphiQL } from "graphiql";
import type { Fetcher, FetcherParams, FetcherOpts } from "@graphiql/toolkit";
import "graphiql/graphiql.css";

import { getApiBaseUrl } from "../../lib/api";
import { useApiHeaders, useGraphQLExplorerEnabled } from "../../lib/api-config";

import styles from "./GraphQLExplorer.module.css";

type GraphQLFetcher = Fetcher;

function createFetcher(endpoint: string, headers: Record<string, string>): GraphQLFetcher {
  return async function graphQLFetcher(params: FetcherParams, fetcherOpts?: FetcherOpts) {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...headers,
        ...(fetcherOpts?.headers ?? {}),
      },
      body: JSON.stringify(params ?? {}),
      credentials: "include",
    });

    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response.text();
  };
}

function normalizeHeaders(headers: Record<string, string>): string {
  const merged = {
    Accept: "application/json",
    ...headers,
  };
  return JSON.stringify(merged, null, 2);
}

export default function GraphQLExplorer(): JSX.Element {
  const enabled = useGraphQLExplorerEnabled();
  const headers = useApiHeaders();

  const endpoint = useMemo(() => `${getApiBaseUrl().replace(/\/$/, "")}/graphql`, []);

  const fetcher = useMemo(() => {
    if (!enabled) {
      return null;
    }
    return createFetcher(endpoint, headers);
  }, [enabled, endpoint, headers]);

  const headerEditorValue = useMemo(() => normalizeHeaders(headers), [headers]);

  if (!enabled) {
    return (
      <main className={`stack ${styles.container}`} id="main-content">
        <header className={`stack ${styles.header}`}>
          <h1 className={styles.title}>GraphQL explorer</h1>
          <p className={styles.subtitle}>
            The GraphQL explorer is disabled for this environment. Contact an administrator if you need
            access.
          </p>
        </header>
      </main>
    );
  }

  if (!fetcher) {
    return <main className={styles.container} id="main-content" />;
  }

  return (
    <main className={styles.container} id="main-content">
      <header className={`stack ${styles.header}`}>
        <h1 className={styles.title}>GraphQL explorer</h1>
        <p className={styles.subtitle}>
          Send authenticated queries directly to the Theoria GraphQL API. Authorization headers from your
          current session are applied automatically.
        </p>
      </header>
      <section className={styles.explorer} aria-label="GraphQL explorer">
        <GraphiQL
          fetcher={fetcher}
          isHeadersEditorEnabled={true}
          defaultEditorToolsVisibility="headers"
          initialHeaders={headerEditorValue}
          defaultHeaders={headerEditorValue}
          shouldPersistHeaders={false}
        />
      </section>
    </main>
  );
}
