// Only public, non-secret values belong here: Next.js embeds these in browser assets.
const demo = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';
export default {
  env: {
    NEXT_PUBLIC_API_URL: demo ? '' : process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000',
  },
};
