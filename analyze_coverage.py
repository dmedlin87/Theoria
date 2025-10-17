#!/usr/bin/env python3
"""Analyze coverage.xml and provide summary report."""
import xml.etree.ElementTree as ET
from pathlib import Path

def analyze_coverage(coverage_file='coverage.xml'):
    tree = ET.parse(coverage_file)
    root = tree.getroot()

    overall_rate = float(root.get('line-rate'))
    lines_valid = int(root.get('lines-valid'))
    lines_covered = int(root.get('lines-covered'))

    print("=" * 80)
    print("THEORIA TEST COVERAGE REPORT")
    print("=" * 80)
    print(f"\nOverall Coverage: {overall_rate:.1%} ({lines_covered:,}/{lines_valid:,} lines)")
    print("Target: 80%")
    print(f"Gap: {(0.80 - overall_rate) * lines_valid:.0f} lines needed")

    # Package-level breakdown
    packages = root.find('packages').findall('package')
    package_data = []

    for package in packages:
        name = package.get('name')
        rate = float(package.get('line-rate'))
        classes = package.find('classes').findall('class')
        package_data.append((name, rate, len(classes)))

    # Sort by coverage rate
    package_data.sort(key=lambda x: x[1])

    print("\n" + "=" * 80)
    print("PACKAGE COVERAGE (sorted by coverage rate)")
    print("=" * 80)
    print(f"{'Package':<40} {'Coverage':>8} {'Files':>8}  Coverage Bar")
    print("-" * 80)

    for name, rate, file_count in package_data:
        coverage_bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
        print(f"{name:<40} {rate:>7.1%} {file_count:>8}  {coverage_bar}")

    # Find packages below 50%
    low_coverage = [(n, r, f) for n, r, f in package_data if r < 0.5]

    if low_coverage:
        print("\n" + "=" * 80)
        print(f"PACKAGES BELOW 50% COVERAGE ({len(low_coverage)} packages)")
        print("=" * 80)
        for name, rate, _file_count in low_coverage:
            print(f"  • {name:<57} {rate:>7.1%}")

    # Find packages with 0% coverage
    no_coverage = [(n, r, f) for n, r, f in package_data if r == 0.0]

    if no_coverage:
        print("\n" + "=" * 80)
        print(f"PACKAGES WITH NO COVERAGE ({len(no_coverage)} packages)")
        print("=" * 80)
        for name, _rate, _file_count in no_coverage:
            print(f"  • {name}")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze_coverage()
