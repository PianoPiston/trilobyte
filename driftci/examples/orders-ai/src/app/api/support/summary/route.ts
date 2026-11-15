import { NextResponse } from "next/server";
import { z } from "zod";
import { MAX_SUMMARY_TOKENS, SUMMARY_MODEL, openai } from "@/lib/ai";

const input = z.object({ transcript: z.string().min(1).max(40_000) });

export async function POST(request: Request) {
  const parsed = input.safeParse(await request.json());
  if (!parsed.success) return NextResponse.json({ error: "Invalid transcript" }, { status: 400 });
  const completion = await openai.chat.completions.create({
    model: SUMMARY_MODEL,
    max_tokens: MAX_SUMMARY_TOKENS,
    temperature: 0,
    messages: [
      { role: "system", content: "Summarize the support interaction. Do not invent order facts." },
      { role: "user", content: parsed.data.transcript },
    ],
  });
  return NextResponse.json({ summary: completion.choices[0]?.message.content });
}
