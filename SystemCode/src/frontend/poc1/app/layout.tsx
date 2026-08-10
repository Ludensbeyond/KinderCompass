import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KinderCompass",
  description: "Find a preschool that fits your child and your family's day.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

