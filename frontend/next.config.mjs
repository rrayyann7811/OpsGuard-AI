// Public build-time values only; never pass credentials here.
const demo = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';
const hosted = process.env.NEXT_PUBLIC_HOSTED_API === 'true';
if (demo && hosted) throw new Error('Choose either synthetic demo or hosted API mode');
if (hosted) {
  const url = new URL(process.env.NEXT_PUBLIC_API_URL || '');
  if (
    url.protocol !== 'https:' ||
    !url.hostname ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    (url.pathname !== '/' && url.pathname !== '') ||
    /^(localhost|127\.|0\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[.*\])/.test(url.hostname) ||
    url.hostname.endsWith('.localhost') ||
    url.hostname.endsWith('.local')
  ) {
    throw new Error('Hosted mode requires a public HTTPS API origin without credentials or paths');
  }
}
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: demo
      ? ''
      : hosted
        ? process.env.NEXT_PUBLIC_API_URL
        : process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000',
  },
};

export default nextConfig;
