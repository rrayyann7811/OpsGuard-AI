// Build-time, public setting. Never put credentials in NEXT_PUBLIC variables.
export const isPublicDemo = process.env.NEXT_PUBLIC_DEMO_MODE === 'true';
