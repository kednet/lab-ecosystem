import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://app.pulab.ru',
  integrations: [tailwind()],
  output: "static",

  build: {
    format: 'directory',
  },

  vite: {
    build: {
      assetsInlineLimit: 0,
    },
  },
});
