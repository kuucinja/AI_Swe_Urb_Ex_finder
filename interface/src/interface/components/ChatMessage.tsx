import { Bot, UserRound } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "../../retrieval/types";

type ChatMessageProps = {
  message: ChatMessageType;
};

export function ChatMessage({ message }: ChatMessageProps) {
  const isAssistant = message.role === "assistant";

  return (
    <div
      className={`flex items-start gap-3 ${isAssistant ? "justify-start" : "justify-end"}`}
    >
      {isAssistant ? (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
          <Bot className="h-4 w-4" />
        </div>
      ) : null}

      <div
        className={`max-w-[85%] rounded-3xl border px-4 py-3 text-sm leading-6 shadow-lg ${
          isAssistant
            ? "border-white/10 bg-white/5 text-slate-100"
            : "border-cyan-400/20 bg-cyan-500/15 text-cyan-50"
        }`}
      >
        <p className="whitespace-pre-wrap">  {typeof message.content === "string"
    ? message.content
    : message.content.answer}</p>
      </div>

      {!isAssistant ? (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
          <UserRound className="h-4 w-4" />
        </div>
      ) : null}
    </div>
  );
}
