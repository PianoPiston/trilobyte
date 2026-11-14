export default function Developers() {
  const origin = window.location.origin;
  return (
    <div className="page dev">
      <h1 className="page-title">API &amp; MCP</h1>
      <p>Everything in the UI is one HTTP API, and the same functions are exposed to AI agents as an MCP server.</p>
      <h2>Architecture</h2>
      <div className="arch">
        <div className="col"><div className="box in">Drawing<br /><small>PNG · PDF · DXF · IFC · scans</small></div></div>
        <div className="arrow">→</div>
        <div className="col"><div className="box">Format router</div></div>
        <div className="arrow">→</div>
        <div className="col stack">
          <div className="box exact">DXF / IFC parsers<br /><small>exact, CPU</small></div>
          <div className="box model">Detector + fine-tuned VLM<br /><small>Qwen3.5-4B LoRA, trained on Verda</small></div>
          <div className="box ctx">Historic context<br /><small>archive records + web</small></div>
        </div>
        <div className="arrow">→</div>
        <div className="col"><div className="box std">Standardized drawing file<br /><small>rooms · doors · windows · IDs · provenance</small></div></div>
        <div className="arrow">→</div>
        <div className="col"><div className="box out">Answer + evidence + confidence<br /><small>Web · API · MCP</small></div></div>
      </div>
      <h2>HTTP API</h2>
      <pre>{`curl -s ${origin}/api/drawings | jq '.drawings[0].id'
curl -s -X POST ${origin}/api/ask -H 'Content-Type: application/json' \\
  -d '{"drawing_id":"swiss_dwellings~site3634_bldg5596_floor24203","question":"How many apartments are on this floor?"}'
curl -s '${origin}/api/search?q=3%20bedrooms%20and%20a%20sauna'
curl -s ${origin}/api/benchmark`}</pre>
      <p className="small muted">Interactive docs: <a href="/docs">/docs</a> (OpenAPI).</p>
      <h2>MCP server (any MCP client)</h2>
      <p className="small">Tools: <code>ask_drawing</code>, <code>search_drawings</code>, <code>get_drawing</code>, <code>get_drawing_context</code>, <code>list_drawings</code>. Runs over stdio, or streamable HTTP with <code>--http</code>.</p>
      <pre>{`{
  "mcpServers": {
    "stoa-blueprints": {
      "command": "~/venvs/stoa-app/bin/python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/junction"
    }
  }
}`}</pre>
      <pre>{`python -m app.mcp.server            # stdio
python -m app.mcp.server --http     # streamable HTTP`}</pre>
    </div>
  );
}
