import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";

interface LiveAnnouncerContextValue {
  announce: (message: string, politeness?: "polite" | "assertive") => void;
}

const LiveAnnouncerContext = createContext<LiveAnnouncerContextValue>({
  announce: () => {},
});

export function useLiveAnnouncer() {
  return useContext(LiveAnnouncerContext);
}

export function LiveAnnouncerProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [politeMessage, setPoliteMessage] = useState("");
  const [assertiveMessage, setAssertiveMessage] = useState("");
  const clearRef = useRef<ReturnType<typeof setTimeout>>();

  const announce = useCallback(
    (message: string, politeness: "polite" | "assertive" = "polite") => {
      if (clearRef.current) clearTimeout(clearRef.current);

      if (politeness === "assertive") {
        setAssertiveMessage("");
        requestAnimationFrame(() => setAssertiveMessage(message));
      } else {
        setPoliteMessage("");
        requestAnimationFrame(() => setPoliteMessage(message));
      }

      clearRef.current = setTimeout(() => {
        setPoliteMessage("");
        setAssertiveMessage("");
      }, 5000);
    },
    [],
  );

  return (
    <LiveAnnouncerContext.Provider value={{ announce }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="true"
        role="status"
        className="sr-only"
      >
        {politeMessage}
      </div>
      <div
        aria-live="assertive"
        aria-atomic="true"
        role="alert"
        className="sr-only"
      >
        {assertiveMessage}
      </div>
    </LiveAnnouncerContext.Provider>
  );
}
