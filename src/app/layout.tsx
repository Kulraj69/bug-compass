import type { Metadata } from "next";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bug Compass — Every fix starts with finding it",
  description: "An open localization atlas for SWE-bench Lite. Explore import-graph distances, context budgets, and file-retrieval baselines for small coding agents.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><Shell>{children}</Shell></body></html>;
}
