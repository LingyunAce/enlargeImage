import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "EnlargeImage",
  description: "Upscale low-resolution images with SwinIR",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
