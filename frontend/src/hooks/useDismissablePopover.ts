import { useEffect } from "react";

export function useDismissablePopover(openPopover: string | null, closePopover: () => void): void {
  useEffect(() => {
    if (!openPopover) return undefined;

    function closeOnOutsidePointer(event: PointerEvent) {
      const target = event.target;

      if (!(target instanceof Element)) return;
      if (target.closest("[data-popover]") || target.closest("[data-popover-trigger]")) return;

      closePopover();
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closePopover();
      }
    }

    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [openPopover, closePopover]);
}
