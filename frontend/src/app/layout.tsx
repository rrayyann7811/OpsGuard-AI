import type { Metadata } from 'next';
import { Shell } from '@/components/shell';
import './globals.css';
export const metadata: Metadata = {
  title: { default: 'Overview · OpsGuard AI', template: '%s · OpsGuard AI' },
  description:
    'Local RAG-augmented incident investigation with evidence-cited analysis and human review.',
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
