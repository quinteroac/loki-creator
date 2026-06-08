import { getCardDisplayTitle } from "./cardDocuments";
import type { GeneratedCard } from "../types";

export type ActiveCardMention = {
  start: number;
  end: number;
  query: string;
};

export type CardMentionOption = {
  card: GeneratedCard;
  title: string;
};

const CARD_MENTION_PATTERN = /@\[([^\]]+)\]/g;

function normalizeMentionValue(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function dedupeIds(ids: string[]): string[] {
  return ids.filter((id, index) => ids.indexOf(id) === index);
}

export function getActiveCardMention(text: string, cursorIndex: number): ActiveCardMention | null {
  const safeCursorIndex = Math.max(0, Math.min(cursorIndex, text.length));
  const textBeforeCursor = text.slice(0, safeCursorIndex);
  const start = textBeforeCursor.lastIndexOf("@");

  if (start < 0) return null;

  const tokenPrefix = start === 0 ? "" : text[start - 1];
  if (tokenPrefix && !/\s|[(,{]/.test(tokenPrefix)) return null;

  const hasOpeningBracket = text[start + 1] === "[";
  const queryStart = start + (hasOpeningBracket ? 2 : 1);
  const query = text.slice(queryStart, safeCursorIndex);

  if (hasOpeningBracket && query.includes("]")) return null;
  if (!hasOpeningBracket && /[\s[\]]/.test(query)) return null;

  return {
    start,
    end: safeCursorIndex,
    query,
  };
}

export function filterCardMentionOptions(cards: GeneratedCard[], query: string): CardMentionOption[] {
  const normalizedQuery = normalizeMentionValue(query);

  return cards
    .map((card) => ({
      card,
      title: getCardDisplayTitle(card),
    }))
    .filter((option) => !normalizedQuery || normalizeMentionValue(option.title).includes(normalizedQuery));
}

export function insertCardMention(
  text: string,
  mention: ActiveCardMention,
  title: string,
): { cursorIndex: number; text: string } {
  const insertion = `@[${title}]`;
  const nextText = `${text.slice(0, mention.start)}${insertion}${text.slice(mention.end)}`;
  const cursorIndex = mention.start + insertion.length;

  return { text: nextText, cursorIndex };
}

export function resolveMentionedCardIds(cards: GeneratedCard[], text: string): string[] {
  const cardsByTitle = new Map<string, GeneratedCard[]>();

  cards.forEach((card) => {
    const key = normalizeMentionValue(getCardDisplayTitle(card));
    const matches = cardsByTitle.get(key) ?? [];

    cardsByTitle.set(key, [...matches, card]);
  });

  const cardIds: string[] = [];
  let match: RegExpExecArray | null;

  CARD_MENTION_PATTERN.lastIndex = 0;
  while ((match = CARD_MENTION_PATTERN.exec(text)) !== null) {
    const title = normalizeMentionValue(match[1] ?? "");
    const card = cardsByTitle.get(title)?.[0];

    if (card) {
      cardIds.push(card.id);
    }
  }

  return dedupeIds(cardIds);
}

export function mergeSelectedCardIds(selectedCardIds: string[], mentionedCardIds: string[]): string[] {
  return dedupeIds([...selectedCardIds, ...mentionedCardIds]);
}
