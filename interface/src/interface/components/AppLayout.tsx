import { MapView } from "./MapView";
import { ChatPanel } from "./ChatPanel";
import { SidebarHeader } from "./SidebarHeader";

export function AppLayout() {
  return (
    <main className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100 md:flex-row">
      <section className="relative min-h-0 flex-[7] border-b border-white/10 bg-slate-950 md:border-b-0 md:border-r">
        <MapView />
      </section>

      <aside className="flex min-h-0 flex-[3] flex-col bg-slate-950/90 backdrop-blur-xl">
        <SidebarHeader />
        <div className="min-h-0 flex-1">
          <ChatPanel />
        </div>
      </aside>
    </main>
  );
}
