import {
  filterCardMentionOptions,
  getActiveCardMention,
  insertCardMention,
  resolveMentionedCardIds,
} from "./cardMentions";
import type { GeneratedCard } from "../types";

function card(id: string, title: string, prompt = ""): GeneratedCard {
  return {
    id,
    name: title,
    prompt,
    html: "",
    metadata: {
      title,
      description: prompt,
    },
  };
}

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}\nExpected: ${JSON.stringify(expected)}\nActual: ${JSON.stringify(actual)}`);
  }
}

const cards = [
  card("card_1", "Sunset Frame", "Warm color study"),
  card("card_2", "Audio Clip", "Voiceover"),
  card("card_3", "sunset frame", "Duplicate title"),
];

assertEqual(getActiveCardMention("Use @[Sun", 9), { start: 4, end: 9, query: "Sun" }, "detects active mention");
assertEqual(getActiveCardMention("Use @", 5), { start: 4, end: 5, query: "" }, "detects bare @ mention");
assertEqual(getActiveCardMention("Use @Sun", 8), { start: 4, end: 8, query: "Sun" }, "detects bare @ query");
assertEqual(getActiveCardMention("Use @[Sun]", 10), null, "ignores completed mention");
assertEqual(getActiveCardMention("Use x@[Sun", 10), null, "requires a token boundary before mention");

assertEqual(
  insertCardMention("Use @ please", { start: 4, end: 5, query: "" }, "Sunset Frame"),
  { text: "Use @[Sunset Frame] please", cursorIndex: 19 },
  "expands bare @ into a complete bracketed mention",
);

assertEqual(
  insertCardMention("Use @[Sun please", { start: 4, end: 9, query: "Sun" }, "Sunset Frame"),
  { text: "Use @[Sunset Frame] please", cursorIndex: 19 },
  "inserts a complete mention and cursor index",
);

assertEqual(
  filterCardMentionOptions(cards, "sun").map((option) => option.card.id),
  ["card_1", "card_3"],
  "filters mention options case-insensitively",
);

assertEqual(
  resolveMentionedCardIds(cards, "Use @[Sunset Frame] and @[Audio Clip]"),
  ["card_1", "card_2"],
  "resolves multiple complete mentions",
);

assertEqual(resolveMentionedCardIds(cards, "Use @[Sunset"), [], "ignores incomplete mentions");
assertEqual(resolveMentionedCardIds(cards, "Use @[sunset frame]"), ["card_1"], "uses first canvas-order duplicate");

console.log("cardMentions tests passed");
