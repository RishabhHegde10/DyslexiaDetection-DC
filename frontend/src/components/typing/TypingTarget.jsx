export default function TypingTarget({ target, typed, showCaret = true }) {
  const caretIndex = typed.length;
  let charGlobalIndex = 0;

  // Split target by words to ensure clean line-wrapping without mid-word breaks
  const words = target.split(" ");

  return (
    <div className="mt-6 rounded-3xl border border-white/70 bg-white/35 backdrop-blur-xl p-5 shadow-sm">
      <div className="flex flex-wrap gap-y-1.5 text-lg leading-relaxed md:text-xl font-medium tracking-normal">
        {words.map((word, wIdx) => {
          const isLastWord = wIdx === words.length - 1;
          const wordChars = (word + (isLastWord ? "" : " ")).split("");

          return (
            <span key={wIdx} className="inline-flex">
              {wordChars.map((ch) => {
                const i = charGlobalIndex++;
                const isTyped = i < typed.length;
                const typedChar = typed[i];
                const isCorrect = isTyped && typedChar === ch;
                const isWrong = isTyped && !isCorrect;
                const isCaret = showCaret && i === caretIndex;
                const isEndCaret = showCaret && i === target.length - 1 && caretIndex >= target.length;

                return (
                  <span
                    key={i}
                    className={[
                      "relative inline-block whitespace-pre select-none transition-colors duration-100",
                      !isTyped ? "text-slate-400" : isCorrect ? "text-slate-900 font-semibold" : "text-rose-600 font-semibold",
                    ].join(" ")}
                  >
                    {ch}
                    {isWrong ? (
                      <span className="absolute inset-0 -z-10 rounded bg-rose-100/80 border-b-2 border-rose-500" />
                    ) : null}
                    {isCaret ? (
                      <span className="absolute -left-[1.5px] top-1/2 -translate-y-1/2 h-[1.3em] w-[2.5px] rounded-full bg-violet-600 animate-pulse shadow-sm shadow-violet-500/50" />
                    ) : null}
                    {isEndCaret ? (
                      <span className="absolute -right-[1.5px] top-1/2 -translate-y-1/2 h-[1.3em] w-[2.5px] rounded-full bg-violet-600 animate-pulse shadow-sm shadow-violet-500/50" />
                    ) : null}
                  </span>
                );
              })}
            </span>
          );
        })}
      </div>
    </div>
  );
}
