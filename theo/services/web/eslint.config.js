import path from 'node:path';
import { fileURLToPath } from 'node:url';

import js from '@eslint/js';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import promisePlugin from 'eslint-plugin-promise';
import reactPlugin from 'eslint-plugin-react';
import reactHooksPlugin from 'eslint-plugin-react-hooks';
import jsxA11yPlugin from 'eslint-plugin-jsx-a11y';
import theoriaPlugin from './eslint-rules/index.js';
import qualityBaseline from './config/ui-quality-baseline.json' with { type: 'json' };

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const baseTsRules = tsPlugin.configs.recommended.rules;
const stylisticTsRules = tsPlugin.configs.stylistic.rules;

export default [
  {
    ignores: ['node_modules', '.next', 'out'],
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: './tsconfig.json',
        tsconfigRootDir: __dirname,
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        JSX: true,
        jest: true,
        describe: true,
        it: true,
        expect: true,
        beforeEach: true,
        afterEach: true,
        beforeAll: true,
        afterAll: true,
        NodeJS: true,
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      promise: promisePlugin,
      react: reactPlugin,
      'react-hooks': reactHooksPlugin,
      'jsx-a11y': jsxA11yPlugin,
      theoria: theoriaPlugin,
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      ...baseTsRules,
      ...stylisticTsRules,
      ...promisePlugin.configs.recommended.rules,
      ...reactPlugin.configs.recommended.rules,
      ...reactHooksPlugin.configs.recommended.rules,
      ...jsxA11yPlugin.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/consistent-type-definitions': 'off',
      '@typescript-eslint/consistent-indexed-object-style': 'off',
      '@typescript-eslint/array-type': 'off',
      'promise/always-return': 'off',
      'react/no-unknown-property': 'off',
      'jsx-a11y/label-has-associated-control': 'off',
      'jsx-a11y/no-noninteractive-tabindex': 'off',
      'no-redeclare': 'off',
      'no-useless-escape': 'off',
      'theoria/no-inline-styles': [
        'error',
        {
          rootDir: __dirname,
          allowances: qualityBaseline.inlineStyleAllowance,
          default: 0,
        },
      ],
      'theoria/component-max-lines': [
        'error',
        {
          rootDir: __dirname,
          allowances: qualityBaseline.componentLineAllowance,
          defaultMax: qualityBaseline.componentDefaultMax,
        },
      ],
    },
  },
  {
    files: ['next-env.d.ts'],
    rules: {
      '@typescript-eslint/triple-slash-reference': 'off',
    },
  },
];
