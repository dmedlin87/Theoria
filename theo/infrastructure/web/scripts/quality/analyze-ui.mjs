#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const projectRoot = path.resolve(__dirname, '../../');
const srcRoot = path.join(projectRoot, 'app');

const IGNORED_DIRS = new Set(['__tests__', '__mocks__', 'node_modules', '.next']);

async function collectTsxFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue;
    if (IGNORED_DIRS.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectTsxFiles(fullPath));
    } else if (entry.isFile() && entry.name.endsWith('.tsx')) {
      files.push(fullPath);
    }
  }
  return files;
}

function isComponentName(name) {
  return /^(?:[A-Z]|use[A-Z])/.test(name) || /Page$/.test(name) || /Layout$/.test(name);
}

function nodeContainsJsx(node) {
  let found = false;
  function visit(n) {
    if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n)) {
      found = true;
      return;
    }
    ts.forEachChild(n, visit);
  }
  visit(node);
  return found;
}

function analyzeComponent(node, sourceFile, name) {
  const start = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
  const end = sourceFile.getLineAndCharacterOfPosition(node.end).line + 1;
  return {
    name,
    lines: end - start + 1,
    start,
    end,
  };
}

function analyzeFile(filePath) {
  const text = ts.sys.readFile(filePath, 'utf8');
  if (!text) {
    return { inlineStyles: 0, components: [] };
  }
  const sourceFile = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let inlineStyles = 0;
  const components = [];

  function recordComponent(node, name) {
    if (!name) return;
    if (!isComponentName(name)) return;
    if (!nodeContainsJsx(node)) return;
    components.push(analyzeComponent(node, sourceFile, name));
  }

  function visit(node) {
    if (ts.isJsxAttribute(node) && node.name.text === 'style') {
      inlineStyles += 1;
    }

    if (ts.isFunctionDeclaration(node) && node.name) {
      recordComponent(node, node.name.text);
    } else if (ts.isVariableStatement(node)) {
      for (const declaration of node.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name)) continue;
        const identifier = declaration.name.text;
        const initializer = declaration.initializer;
        if (!initializer) continue;
        if (ts.isArrowFunction(initializer) || ts.isFunctionExpression(initializer)) {
          recordComponent(initializer, identifier);
        }
      }
    } else if (ts.isClassDeclaration(node) && node.name) {
      const heritage = node.heritageClauses;
      const extendsReactComponent = heritage?.some((clause) =>
        clause.types.some((t) => {
          const text = t.expression.getText(sourceFile);
          return text === 'Component' || text === 'React.Component' || text.endsWith('.Component');
        })
      );
      if (extendsReactComponent) {
        recordComponent(node, node.name.text);
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);

  return { inlineStyles, components };
}

export async function analyzeUi() {
  const files = await collectTsxFiles(srcRoot);
  const metrics = {
    inlineStyles: {
      total: 0,
      byFile: {},
    },
    components: {
      byFile: {},
      largest: [],
    },
  };

  for (const file of files) {
    const relative = path.relative(projectRoot, file).replace(/\\/g, '/');
    const { inlineStyles, components } = analyzeFile(file);
    metrics.inlineStyles.total += inlineStyles;
    metrics.inlineStyles.byFile[relative] = inlineStyles;
    if (components.length > 0) {
      metrics.components.byFile[relative] = components;
      metrics.components.largest.push(
        ...components.map((component) => ({ ...component, file: relative }))
      );
    }
  }

  metrics.components.largest.sort((a, b) => b.lines - a.lines);

  return metrics;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const metrics = await analyzeUi();
  console.log(JSON.stringify(metrics, null, 2));
}
