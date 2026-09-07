import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { Footer, Header } from "@/components/common";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Chase 201 — Every decision counts",
    template: "%s · Chase 201",
  },
  description:
    "Draft your XI. Call your shots. Chase 201 in a single-player cricket strategy game.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <Providers>
          <a className="skip-link" href="#main">
            Skip to content
          </a>
          <Header />
          <main id="main">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
