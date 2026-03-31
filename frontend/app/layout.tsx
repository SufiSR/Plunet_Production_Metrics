import type { Metadata } from "next";
import { ReactNode } from "react";

export const metadata: Metadata = {
  title: "DORA Metrics",
  description: "DORA metrics dashboard"
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
