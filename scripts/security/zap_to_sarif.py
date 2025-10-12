#!/usr/bin/env python3
"""Convert OWASP ZAP baseline JSON reports into SARIF v2.1.0."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _risk_to_level(risk: str) -> str:
    normalized = (risk or "").strip().lower()
    if normalized in {"high", "very high"}:
        return "error"
    if normalized in {"medium"}:
        return "error"
    if normalized in {"low"}:
        return "warning"
    return "note"


def _alert_instances(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    instances = alert.get("instances")
    if instances:
        return instances
    # When no discrete instances are recorded, synthesize a single one using the
    # primary URI for the alert so SARIF consumers can still display a location.
    fallback_uri = alert.get("uri") or alert.get("url") or ""
    return [{"uri": fallback_uri, "method": alert.get("method", "GET")}]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: zap_to_sarif.py <input-json> <output-sarif>")

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    data = json.loads(input_path.read_text())

    rules: Dict[str, Dict[str, Any]] = {}
    results: List[Dict[str, Any]] = []

    for site in data.get("site", []):
        site_name = site.get("@name") or site.get("name") or "unknown-site"
        for alert in site.get("alerts", []):
            plugin_id = str(
                alert.get("pluginId")
                or alert.get("pluginid")
                or alert.get("id")
                or alert.get("alertRef")
                or alert.get("name")
                or "zap-alert"
            )
            title = alert.get("name") or f"ZAP finding {plugin_id}"
            description = alert.get("description") or ""
            solution = alert.get("solution") or ""
            references = alert.get("reference") or ""
            cwe = alert.get("cweid")
            level = _risk_to_level(alert.get("risk") or alert.get("riskdesc", ""))

            if plugin_id not in rules:
                rules[plugin_id] = {
                    "id": plugin_id,
                    "name": title,
                    "shortDescription": {"text": title[:256]},
                    "fullDescription": {"text": description[:8192]},
                    "help": {
                        "text": "\n".join(
                            filter(
                                None,
                                [
                                    description.strip(),
                                    solution.strip(),
                                    f"References: {references}" if references else "",
                                ],
                            )
                        )
                        or description[:8192],
                    },
                }
                if cwe:
                    rules[plugin_id]["properties"] = {"cwe": f"CWE-{cwe}"}

            for instance in _alert_instances(alert):
                uri = instance.get("uri") or instance.get("url") or site_name
                method = instance.get("method") or "GET"
                message = instance.get("evidence") or alert.get("alert") or title

                results.append(
                    {
                        "ruleId": plugin_id,
                        "level": level,
                        "message": {"text": message[:8192]},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": uri},
                                },
                                "logicalLocations": [
                                    {
                                        "name": site_name,
                                        "fullyQualifiedName": f"{method} {uri}",
                                    }
                                ],
                            }
                        ],
                    }
                )

    sarif_output = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "OWASP ZAP Baseline",
                        "informationUri": "https://www.zaproxy.org/docs/desktop/start/features/scanners/",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }

    output_path.write_text(json.dumps(sarif_output, indent=2))


if __name__ == "__main__":
    main()
