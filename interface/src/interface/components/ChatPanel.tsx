import { LoaderCircle, MessageSquareMore } from "lucide-react";
import { useState } from "react";
import { useAutoScroll } from "../../retrieval/hooks/useAutoScroll";
import { useAppStore } from "../../retrieval/store/useAppStore";
import { ChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";

export function ChatPanel() {
  const [draft, setDraft] = useState("");
  const messages = useAppStore((state) => state.messages);
  const isChatLoading = useAppStore((state) => state.isChatLoading);
  const sendMessage = useAppStore((state) => state.sendMessage);
  const error = useAppStore((state) => state.error);

  const endRef = useAutoScroll(messages);

  async function handleSend() {
    if (!draft.trim() || isChatLoading) return;
    const message = draft;
    setDraft("");
    await sendMessage(message);
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-slate-950/70 backdrop-blur-xl">
      <div className="border-b border-white/10 px-5 py-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-slate-400">
          <MessageSquareMore className="h-3.5 w-3.5 text-cyan-200" />
          agent chat
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-400">
          Use the assistant to surface likely Urbex locations and push matching pins on the map.
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-4">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {isChatLoading ? (
            <div className="flex items-center gap-3 text-sm text-slate-400">
              <LoaderCircle className="h-4 w-4 animate-spin text-cyan-200" />
              Thinking through the clue set...
            </div>
          ) : null}

          {error ? (
            <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
              {error}
            </div>
          ) : null}

          <div ref={endRef} />
        </div>
      </div>

      <ChatInput
        value={draft}
        onChange={setDraft}
        onSubmit={handleSend}
        disabled={isChatLoading}
      />
    </section>
  );
}
