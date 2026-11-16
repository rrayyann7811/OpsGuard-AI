// Build-time, public setting. Never put credentials in NEXT_PUBLIC variables.
export const isPublicDemo = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';
export const isHostedApi = process.env.NEXT_PUBLIC_HOSTED_API === 'true';
