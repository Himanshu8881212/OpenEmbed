import { Fraunces, Instrument_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({ subsets: ["latin"], variable: "--f-fraunces", axes: ["opsz", "SOFT"], display: "swap" });
const instrument = Instrument_Sans({ subsets: ["latin"], variable: "--f-instrument", display: "swap" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--f-jetbrains", display: "swap" });

export const metadata = { title: "Knowledge Store", description: "Store company material, search it with evidence, and connect applications." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${instrument.variable} ${jetbrains.variable}`}>
      <body>
        <a className="skip" href="#main">Skip to content</a>
        {children}
      </body>
    </html>
  );
}
