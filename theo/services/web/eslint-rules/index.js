import path from 'node:path';

function normalizePath(filePath, rootDir) {
  const relative = path.relative(rootDir, filePath);
  return relative.split(path.sep).join('/');
}

const INLINE_STYLE_MESSAGE = 'Inline style usage exceeds the allowed baseline for {{file}} ({{count}} > {{limit}}).';

function isComponentName(name) {
  return /^(?:[A-Z]|use[A-Z])/.test(name) || /Page$/.test(name) || /Layout$/.test(name);
}

function containsJsx(node) {
  let found = false;
  const visited = new Set();

  function visit(current) {
    if (!current || found || visited.has(current)) return;
    visited.add(current);

    if (current.type === 'JSXElement' || current.type === 'JSXFragment') {
      found = true;
      return;
    }

    for (const key of Object.keys(current)) {
      if (key === 'parent') continue;
      const value = current[key];
      if (!value) continue;
      if (Array.isArray(value)) {
        for (const item of value) {
          if (item && typeof item.type === 'string') {
            visit(item);
            if (found) return;
          }
        }
      } else if (typeof value === 'object' && typeof value.type === 'string') {
        visit(value);
        if (found) return;
      }
    }
  }

  if (node.body) {
    visit(node.body);
  } else {
    visit(node);
  }

  return found;
}

function getFunctionLines(node, sourceCode) {
  const target = node.type === 'VariableDeclarator' ? node.init : node;
  const locNode = target && target.loc ? target : node;
  const start = locNode.loc?.start.line ?? sourceCode.getLocFromIndex(locNode.range[0]).line;
  const end = locNode.loc?.end.line ?? sourceCode.getLocFromIndex(locNode.range[1]).line;
  return end - start + 1;
}

const noInlineStylesRule = {
  meta: {
    type: 'problem',
    docs: {
      description: 'Prevents inline styles from exceeding the tracked baseline.',
    },
    schema: [
      {
        type: 'object',
        properties: {
          rootDir: { type: 'string' },
          allowances: { type: 'object' },
          default: { type: 'number' },
        },
        additionalProperties: false,
      },
    ],
    messages: {
      exceeded: INLINE_STYLE_MESSAGE,
    },
  },
  create(context) {
    const options = context.options[0] ?? {};
    const rootDir = options.rootDir ?? process.cwd();
    const allowances = options.allowances ?? {};
    const defaultLimit = options.default ?? 0;
    const filePath = normalizePath(context.getFilename(), rootDir);
    const limit = allowances[filePath] ?? defaultLimit;
    let count = 0;

    return {
      JSXAttribute(node) {
        if (node.name && node.name.name === 'style') {
          count += 1;
          if (count > limit) {
            context.report({
              node,
              messageId: 'exceeded',
              data: { file: filePath, count, limit },
            });
          }
        }
      },
      'Program:exit'() {
        count = 0;
      },
    };
  },
};

const componentMaxLinesRule = {
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Ensures React components remain below the configured line threshold.',
    },
    schema: [
      {
        type: 'object',
        properties: {
          rootDir: { type: 'string' },
          allowances: { type: 'object' },
          defaultMax: { type: 'number' },
        },
        additionalProperties: false,
      },
    ],
    messages: {
      tooLarge: 'Component {{name}} in {{file}} is {{lines}} lines (limit {{limit}}).',
    },
  },
  create(context) {
    const options = context.options[0] ?? {};
    const rootDir = options.rootDir ?? process.cwd();
    const allowances = options.allowances ?? {};
    const defaultMax = options.defaultMax ?? 400;
    const filePath = normalizePath(context.getFilename(), rootDir);
    const limit = allowances[filePath] ?? defaultMax;
    const sourceCode = context.getSourceCode();

    function checkFunction(node, name) {
      if (!name || !isComponentName(name)) return;
      if (!containsJsx(node)) return;
      const lines = getFunctionLines(node, sourceCode);
      if (lines > limit) {
        context.report({
          node,
          messageId: 'tooLarge',
          data: { name, file: filePath, lines, limit },
        });
      }
    }

    return {
      FunctionDeclaration(node) {
        if (node.id) {
          checkFunction(node, node.id.name);
        }
      },
      VariableDeclarator(node) {
        if (node.id && node.id.type === 'Identifier' && node.init && (node.init.type === 'ArrowFunctionExpression' || node.init.type === 'FunctionExpression')) {
          checkFunction(node.init, node.id.name);
        }
      },
      ClassDeclaration(node) {
        if (!node.id) return;
        const superClass = node.superClass;
        if (!superClass) return;
        let inheritsReactComponent = false;
        if (superClass.type === 'MemberExpression') {
          const object = superClass.object;
          const property = superClass.property;
          inheritsReactComponent =
            (object.type === 'Identifier' && object.name === 'React' && property.type === 'Identifier' && property.name === 'Component') ||
            (property.type === 'Identifier' && property.name === 'Component');
        } else if (superClass.type === 'Identifier') {
          inheritsReactComponent = superClass.name === 'Component';
        }
        if (inheritsReactComponent) {
          checkFunction(node, node.id.name);
        }
      },
    };
  },
};

export default {
  rules: {
    'no-inline-styles': noInlineStylesRule,
    'component-max-lines': componentMaxLinesRule,
  },
};
