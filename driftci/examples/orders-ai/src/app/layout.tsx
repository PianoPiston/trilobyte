import type { ReactNode } from "react";

export const metadata = { title: "Orders AI", description: "Support operations workspace" };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
