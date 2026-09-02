import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Copy Trading",
  description: "AI Copy Trading foundation",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
