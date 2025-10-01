module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    tsconfigRootDir: __dirname,
  },
  plugins: ['@typescript-eslint', 'promise'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:promise/recommended',
    'next/core-web-vitals',
  ],
  ignorePatterns: ['.next/**', 'out/**', 'node_modules/**'],
  rules: {
    '@typescript-eslint/no-unused-vars': [
      'error',
      { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
    ],
    'promise/always-return': 'off',
    'react-hooks/rules-of-hooks': 'off',
    'react-hooks/exhaustive-deps': 'off',
    'no-constant-condition': 'off',
    'no-useless-escape': 'off',
    '@typescript-eslint/no-require-imports': 'off',
  },
};
