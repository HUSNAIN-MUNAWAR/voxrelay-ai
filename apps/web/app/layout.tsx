import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = { title:'VoxRelay AI — Voice Operations', description:'Enterprise voice AI operations control center.' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }
