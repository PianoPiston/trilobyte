// Run inside the application's own CI, never by DriftCI's repository scanner.
// The check gate is explicit so a model migration cannot silently merge.
const endpoint = process.env.MODEL_EVAL_URL;
if (!endpoint) {
  console.log("Set MODEL_EVAL_URL to run the private support-quality evaluation suite.");
  process.exit(0);
}
const response = await fetch(endpoint, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ suite: "support-summary-v3", candidate: process.env.CANDIDATE_MODEL }),
});
if (!response.ok) throw new Error(`Evaluation failed: ${response.status}`);
console.log(await response.json());
