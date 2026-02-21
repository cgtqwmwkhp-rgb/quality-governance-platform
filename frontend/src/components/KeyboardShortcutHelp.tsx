import { useState, useMemo } from "react";
import { Keyboard } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "./ui/Dialog";
import {
  getRegisteredShortcuts,
  useKeyboardShortcuts,
} from "../hooks/useKeyboardShortcuts";

function formatKey(key: string): string {
  const map: Record<string, string> = {
    meta: "⌘",
    ctrl: "⌃",
    alt: "⌥",
    shift: "⇧",
  };
  return map[key] || key.charAt(0).toUpperCase() + key.slice(1);
}

export default function KeyboardShortcutHelp() {
  const [open, setOpen] = useState(false);

  useKeyboardShortcuts([
    {
      key: "?",
      modifiers: ["shift"],
      description: "Show keyboard shortcuts",
      action: () => setOpen(true),
      scope: "Global",
    },
  ]);

  const grouped = useMemo(() => {
    if (!open) return {};
    const shortcuts = getRegisteredShortcuts();
    const groups: Record<string, typeof shortcuts> = {};
    for (const s of shortcuts) {
      const scope = s.scope || "General";
      if (!groups[scope]) groups[scope] = [];
      groups[scope].push(s);
    }
    return groups;
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard className="w-5 h-5 text-primary" />
            Keyboard Shortcuts
          </DialogTitle>
          <DialogDescription>
            Available shortcuts in this application
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 max-h-[60vh] overflow-y-auto pr-1">
          {Object.entries(grouped).map(([scope, shortcuts]) => (
            <div key={scope}>
              <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">
                {scope}
              </h3>
              <div className="space-y-1">
                {shortcuts.map((s) => {
                  const mods = s.modifiers || [];
                  const keys = [...mods.map(formatKey), formatKey(s.key)];
                  return (
                    <div
                      key={`${mods.sort().join("+")}+${s.key}`}
                      className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-surface transition-colors"
                    >
                      <span className="text-sm text-foreground">
                        {s.description}
                      </span>
                      <div className="flex items-center gap-1">
                        {keys.map((k, i) => (
                          <kbd
                            key={i}
                            className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 text-xs font-medium bg-surface border border-border rounded-md text-muted-foreground shadow-sm"
                          >
                            {k}
                          </kbd>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {Object.keys(grouped).length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No shortcuts registered
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
