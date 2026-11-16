const ROUTES = [
  ["DXF and IFC parsers", "Exact values computed on CPU from the CAD or BIM source file."],
  ["Symbol detector", "Doors, windows, fixtures and rooms found on raster plans and uploads."],
  ["Printed text", "PDF vector text or OCR, with room labels matched to their areas."],
  ["Fine-tuned Qwen3.5-4B", "A LoRA adapter trained on Verda GPUs. Confidence comes from the answer-token probabilities."],
  ["Archive context", "Record fields and web results for historic drawings, each with its source link."],
];

export default function Developers() {
  const origin = window.location.origin;
  return (
    <div className="page narrow dev">
      <h1>API and MCP server</h1>
      <p className="lead">The web interface runs on one HTTP API. The same functions are available to AI agents through an MCP server.</p>

      <h2>How a question is answered</h2>
      <p>Every drawing is converted into one standardized file of rooms, openings, symbols and elements with ids and provenance. A question collects candidate answers from each route below. Calibrated rules rank the candidates, and an answer under 99% expected precision is returned as “needs check” together with its evidence.</p>
      <dl className="routes">
        {ROUTES.map(([name, text]) => <div key={name}><dt>{name}</dt><dd>{text}</dd></div>)}
      </dl>

      <h2>HTTP API</h2>
      <pre>{`curl -s ${origin}/api/drawings | jq '.drawings[0].id'

curl -s -X POST ${origin}/api/ask -H 'Content-Type: application/json' \\
  -d '{"drawing_id":"swiss_dwellings~site3634_bldg5596_floor24203",
       "question":"How many apartments are on this floor?"}'

curl -s -F file=@plan.pdf ${origin}/api/upload
curl -s '${origin}/api/search?q=3%20bedrooms%20and%20a%20sauna'

# rooms, areas, perimeters and scale of a drawing; live material unit prices
curl -s '${origin}/x/takeoff/swiss_dwellings~site3634_bldg5596_floor24203'
curl -s '${origin}/x/prices'`}</pre>
      <p>The OpenAPI reference is at <a href="/docs">/docs</a>.</p>

      <h2>MCP server</h2>
      <p>Tools: <code>ask_drawing</code>, <code>search_drawings</code>, <code>get_drawing</code>, <code>get_drawing_context</code> and <code>list_drawings</code>. The server runs over stdio, or over streamable HTTP with <code>--http</code>.</p>
      <pre>{`{
  "mcpServers": {
    "trilobyte": {
      "command": "~/venvs/stoa-app/bin/python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/junction"
    }
  }
}`}</pre>
    </div>
  );
}
