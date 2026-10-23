import type { Metadata } from "next";
import { Shell } from "@/components/shell";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "FantasyAdvisor · NFL Fantasy Intelligence",
    template: "%s · FantasyAdvisor",
  },
  description:
    "Full-PPR NFL projections, player research, and start/sit decisions grounded in historical data.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
