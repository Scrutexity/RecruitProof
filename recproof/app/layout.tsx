import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RecruitProof · Million CV Proof Dashboard",
  description: "Enterprise demo shell for proving hidden candidate value inside existing CV archives.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
