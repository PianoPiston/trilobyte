import OpenAI from "openai";

export const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// Shared by the support summary route and its offline evaluation.
export const SUMMARY_MODEL = "gpt-4-0314" as const;
export const MAX_SUMMARY_TOKENS = 220;
