export function filterBySearch(items, searchValue) {
  const query = searchValue.trim().toLowerCase();

  if (!query) return items;

  return items.filter((item) => item.toLowerCase().includes(query));
}

export function toggleExclusiveAutoSelection(currentSelection, item, autoItem = "Auto") {
  if (item === autoItem) return [autoItem];

  const withoutAuto = currentSelection.filter((selectedItem) => selectedItem !== autoItem);

  if (withoutAuto.includes(item)) {
    const nextSelection = withoutAuto.filter((selectedItem) => selectedItem !== item);
    return nextSelection.length > 0 ? nextSelection : [autoItem];
  }

  return [...withoutAuto, item];
}

export function toggleMultiSelection(currentSelection, item) {
  if (currentSelection.includes(item)) {
    return currentSelection.filter((selectedItem) => selectedItem !== item);
  }

  return [...currentSelection, item];
}

export function getFirstSelectedCardLabel(cards, selectedCardIds, fallbackLabel) {
  const selectedCard = cards.find((card) => selectedCardIds.includes(card.id));

  return selectedCard?.name ?? selectedCard?.id ?? fallbackLabel;
}
