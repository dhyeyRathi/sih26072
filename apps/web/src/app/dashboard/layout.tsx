import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard | SIH26072 Nowcasting",
  description: "Operational Thunderstorm & Lightning Nowcasting Dashboard",
};

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex flex-col h-screen w-full bg-[var(--surface)] text-slate-300 overflow-hidden">
      {children}
    </div>
  );
}
