export default function NodeDetailsPanel({ nodePayload, loading, error }) {
  return (
    <section className="panel node-panel">
      <h2>Node Details</h2>

      {loading && <p className="muted">Loading node...</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && !nodePayload && <p className="muted">Select a node to view metadata.</p>}

      {!loading && !error && nodePayload && (
        <>
          <div className="node-header">
            <div className="node-id">{nodePayload.node?.id}</div>
            <div className="badge">{nodePayload.node?.node_type || "Unknown"}</div>
          </div>

          <h3>Attributes</h3>
          <div className="kv-list">
            {Object.entries(nodePayload.node || {}).map(([key, value]) => (
              <div className="kv-row" key={key}>
                <span className="kv-key">{key}</span>
                <span className="kv-value">{String(value)}</span>
              </div>
            ))}
          </div>

          <h3>Connected Edges</h3>
          <p className="muted">
            Incoming: {(nodePayload.edges?.incoming || []).length} | Outgoing:{" "}
            {(nodePayload.edges?.outgoing || []).length}
          </p>
        </>
      )}
    </section>
  );
}

