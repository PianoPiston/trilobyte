import OpenAI from "openai";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

export async function classifyPriority(subject: string) {
  const result = await client.chat.completions.create({
    model: "o1-mini",
    messages: [{ role: "user", content: `Classify priority low, normal, or urgent: ${subject}` }],
  });
  return result.choices[0]?.message.content?.trim().toLowerCase() ?? "normal";
}
