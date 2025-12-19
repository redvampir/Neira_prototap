import "./globals.css";

export const metadata = {
  title: "NEIRA — Ритуал рождения",
  description: "Neira v2: organism → manifestation → ritual",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body className="min-h-dvh bg-black text-white">{children}</body>
    </html>
  );
}
