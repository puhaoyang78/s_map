import js from '@eslint/js';
import pluginVue from 'eslint-plugin-vue';
import prettierConfig from 'eslint-config-prettier';

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'public/**', 'src/App.js'],
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  prettierConfig,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        window: 'readonly',
        document: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        URLSearchParams: 'readonly',
        CustomEvent: 'readonly',
        fetch: 'readonly',
        Image: 'readonly',
        btoa: 'readonly',
        IntersectionObserver: 'readonly',
      },
    },
    rules: {
      // 允许单词组件名（如 App、Home）
      'vue/multi-word-component-names': 'off',
      // 允许 v-html（项目中 InfoSidebar 使用了它）
      'vue/no-v-html': 'off',
      // 警告 console.log（生产中应移除）
      'no-console': ['warn', { allow: ['error', 'warn', 'log'] }],
      // 未使用变量报错
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
];
