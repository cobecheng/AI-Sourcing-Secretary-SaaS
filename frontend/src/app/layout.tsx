import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Sourcing Secretary",
  description: "Chat-first sourcing assistant for specialty retailers.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

