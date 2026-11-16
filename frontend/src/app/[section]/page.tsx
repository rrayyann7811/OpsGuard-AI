import { notFound } from 'next/navigation';
import { Dashboard } from '@/components/dashboard';
import { navigation } from '@/lib/demo';
export function generateStaticParams() {
  return navigation.filter((item) => item.slug).map((item) => ({ section: item.slug }));
}
export async function generateMetadata({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  return { title: navigation.find((item) => item.slug === section)?.label ?? 'Not found' };
}
export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!navigation.some((item) => item.slug === section)) notFound();
  return <Dashboard slug={section} />;
}
