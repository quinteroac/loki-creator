import { useEffect } from "react";

export function useDismissablePopover(openPopover, closePopover) {
  useEffect(() => {
    if (!openPopover) return undefined;

    function closeOnOutsidePointer(event) {
      const target = event.target;

      if (!(target instanceof Element)) return;
      if (target.closest("[data-popover]") || target.closest("[data-popover-trigger]")) return;

      closePopover();
    }

    function closeOnEscape(event) {
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
