import { SendHorizonal } from "lucide-react";
import type { FormEvent } from "react";

type ChatInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
};

export function ChatInput({ value, onChange, onSubmit, disabled }: ChatInputProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-white/10 bg-slate-950/80 p-4">
      <label className="sr-only" htmlFor="chat-input">
        Send a message
      </label>
      <div className="flex items-end gap-3 rounded-3xl border border-white/10 bg-white/5 p-3 shadow-inner shadow-black/20">
        <textarea
          id="chat-input"
          rows={2}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ask about a ruin, a category, or a clue..."
          className="min-h-[52px] flex-1 resize-none bg-transparent px-1 py-1 text-sm text-slate-100 outline-none placeholder:text-slate-500"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="inline-flex h-11 items-center gap-2 rounded-2xl bg-cyan-400 px-4 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <SendHorizonal className="h-4 w-4" />
          Send
        </button>
      </div>
    </form>
  );
}

