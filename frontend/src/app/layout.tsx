import type { Metadata, Viewport } from "next";
import { Shell } from "@/components/shell";
import { themeInitializer } from "@/lib/theme";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "FantasyAdvisor · NFL Fantasy Intelligence",
    template: "%s · FantasyAdvisor",
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/brand/favicon-32.png", type: "image/png", sizes: "32x32" },
    ],
    apple: "/brand/apple-touch-icon.png",
  },
  description:
    "Full-PPR NFL projections, player research, and start/sit decisions grounded in historical data.",
};
export const viewport: Viewport = { themeColor: "#091b26" };

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeInitializer }} /></head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
