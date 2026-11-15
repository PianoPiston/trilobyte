import OpenAI from "openai";

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

export async function draftEscalation(orderId: string, transcript: string) {
  const response = await client.chat.completions.create({
    model: "gpt-4-0314",
    temperature: 0,
    messages: [
      { role: "system", content: "Draft a calm internal escalation in three bullets." },
      { role: "user", content: `Order ${orderId}: ${transcript.slice(0, 5000)}` },
    ],
  });
  return response.choices[0]?.message.content ?? "Escalation requires manual review.";
}
