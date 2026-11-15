import { NextResponse } from "next/server";

export async function GET() {
  // Fixture response: this example is intentionally not connected to a database.
  return NextResponse.json({ orders: [{ id: "ord_1042", status: "delayed" }] });
}
