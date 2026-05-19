import type { GeneratedCard } from "../types";

export function filterBySearch(items: string[], searchValue: string): string[] {
  const query = searchValue.trim().toLowerCase();

  if (!query) return items;

  return items.filter((item) => item.toLowerCase().includes(query));
}

export function toggleExclusiveAutoSelection(currentSelection: string[], item: string, autoItem = "Auto"): string[] {
  if (item === autoItem) return [autoItem];

  const withoutAuto = currentSelection.filter((selectedItem) => selectedItem !== autoItem);

  if (withoutAuto.includes(item)) {
    const nextSelection = withoutAuto.filter((selectedItem) => selectedItem !== item);
    return nextSelection.length > 0 ? nextSelection : [autoItem];
  }

  return [...withoutAuto, item];
}

export function toggleMultiSelection(currentSelection: string[], item: string): string[] {
  if (currentSelection.includes(item)) {
    return currentSelection.filter((selectedItem) => selectedItem !== item);
  }

  return [...currentSelection, item];
}

export function getFirstSelectedCardLabel(
  cards: GeneratedCard[],
  selectedCardIds: string[],
  fallbackLabel: string,
): string {
  const selectedCard = cards.find((card) => selectedCardIds.includes(card.id));

  return selectedCard?.name ?? selectedCard?.id ?? fallbackLabel;
}
