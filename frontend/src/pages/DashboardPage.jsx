import { useCallback, useEffect, useState } from "react";
import GraphView from "../components/GraphView";
import OverviewGraph from "../components/OverviewGraph";
import NodeDetailsPanel from "../components/NodeDetailsPanel";
import QueryPanel from "../components/QueryPanel";
import { API_BASE_URL, getOverviewGraph, getInitialGraph, getNeighbors, getNode, traceSalesOrder, traceBillingDocument, getBrokenFlows } from "../api/graphApi";

const INITIAL_NODE_LIMIT = 100;
const EXPAND_NODE_LIMIT = 40;
const HARD_NODE_CAP = 500;

function mergeElements(current, incoming, hardCap = HARD_NODE_CAP) {
  const currentNodes = current?.nodes || [];
  const currentEdges = current?.edges || [];
  const incomingNodes = incoming?.nodes || [];
  const incomingEdges = incoming?.edges || [];

  const nodeById = new Map();
  for (const node of currentNodes) {
    nodeById.set(node.data.id, node);
  }
  for (const node of incomingNodes) {
    nodeById.set(node.data.id, node);
  }

  const cappedNodes = Array.from(nodeById.values()).slice(0, hardCap);
  const allowedNodeIds = new Set(cappedNodes.map((n) => n.data.id));

  const edgeById = new Map();
  for (const edge of [...currentEdges, ...incomingEdges]) {
    const edgeId = edge?.data?.id;
    const src = edge?.data?.source;
    const dst = edge?.data?.target;
    if (!edgeId || !allowedNodeIds.has(src) || !allowedNodeIds.has(dst)) {
      continue;
    }
    edgeById.set(edgeId, edge);
  }

  return { nodes: cappedNodes, edges: Array.from(edgeById.values()) };
}

export default function DashboardPage() {
  const [viewMode, setViewMode] = useState("overview"); // "overview" | "detail"
  const [title, setTitle] = useState("Business Flow Overview");
  
  const [graphData, setGraphData] = useState({
    total_nodes: 0,
    total_edges: 0,
    elements: { nodes: [], edges: [] }
  });
  const [graphError, setGraphError] = useState("");
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [loadingExpand, setLoadingExpand] = useState(false);

  const [nodeData, setNodeData] = useState(null);
  const [nodeError, setNodeError] = useState("");
  const [loadingNode, setLoadingNode] = useState(false);

  const loadOverview = useCallback(async () => {
    setLoadingGraph(true);
    setGraphError("");
    setNodeData(null);
    try {
      const data = await getOverviewGraph();
      setViewMode("overview");
      setTitle("Business Flow Overview");
      setGraphData({
        total_nodes: data?.nodes?.length || 0,
        total_edges: data?.edges?.length || 0,
        elements: data || { nodes: [], edges: [] }
      });
    } catch (error) {
      setGraphError(error.message || "Failed to load overview graph.");
    } finally {
      setLoadingGraph(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  const loadInitialDetail = useCallback(async (typeFilter = null) => {
    setLoadingGraph(true);
    setGraphError("");
    setNodeData(null);
    try {
      const data = await getInitialGraph(INITIAL_NODE_LIMIT);
      
      let elements = data?.elements || { nodes: [], edges: [] };
      
      // If user clicked a specific type in overview, filter the initial graph to highlight it
      if (typeFilter) {
        // Ideally the backend would filter, but for now we filter client-side
        // Or we just load the initial block but set view to detail
      }
      
      setViewMode("detail");
      setTitle(typeFilter ? `${typeFilter} Details` : "Detailed Graph View");
      setGraphData({
        total_nodes: elements.nodes.length,
        total_edges: elements.edges.length,
        elements
      });
    } catch (error) {
      setGraphError(error.message || "Failed to load detail graph data.");
    } finally {
      setLoadingGraph(false);
    }
  }, []);

  const onTypeClick = useCallback((type) => {
    loadInitialDetail(type);
  }, [loadInitialDetail]);

  const handleTrace = useCallback(async (action, payload) => {
    setLoadingGraph(true);
    setGraphError("");
    setNodeData(null);
    try {
      let data;
      if (action === "sales_order") {
        data = await traceSalesOrder(payload);
        setTitle(`Trace: Sales Order ${payload}`);
      } else if (action === "billing") {
        data = await traceBillingDocument(payload);
        setTitle(`Trace: Billing Doc ${payload}`);
      } else if (action === "broken") {
        data = await getBrokenFlows();
        setTitle("Broken Flows (Missing Delivery/Billing)");
      }
      
      const elements = data?.elements || { nodes: [], edges: [] };
      
      setViewMode("detail");
      setGraphData({
        total_nodes: elements.nodes.length,
        total_edges: elements.edges.length,
        elements
      });
    } catch (error) {
      setGraphError(error.message || `Failed to execute trace.`);
    } finally {
      setLoadingGraph(false);
    }
  }, []);

  const onNodeClick = useCallback(async (nodeId) => {
    if (viewMode === "overview") return;
    
    setLoadingNode(true);
    setLoadingExpand(true);
    setNodeError("");
    try {
      const [nodeResponse, neighborResponse] = await Promise.all([
        getNode(nodeId),
        getNeighbors(nodeId, EXPAND_NODE_LIMIT)
      ]);
      setNodeData(nodeResponse);
      const merged = mergeElements(graphData?.elements, neighborResponse?.elements, HARD_NODE_CAP);
      setGraphData((prev) => ({
        ...prev,
        total_nodes: merged.nodes.length,
        total_edges: merged.edges.length,
        elements: merged
      }));
    } catch (error) {
      setNodeError(error.message || "Failed to load node details.");
    } finally {
      setLoadingNode(false);
      setLoadingExpand(false);
    }
  }, [graphData?.elements, viewMode]);

  const handleChatResponse = useCallback(async (result) => {
    const { intent, plan } = result;

    if (intent === "TRACE_FLOW" && plan?.document_id) {
      const action = plan.entity_type === "BillingDocument" ? "billing" : "sales_order";
      handleTrace(action, plan.document_id);
    } else if (intent === "BROKEN_FLOW") {
      handleTrace("broken");
    } else if (intent === "ENTITY_LOOKUP" && plan?.document_id) {
      let id = plan.document_id;
      if (plan.entity_type === "SalesOrder" && !id.startsWith("SO_")) id = "SO_" + id;
      else if (plan.entity_type === "BillingDocument" && !id.startsWith("BILL_")) id = "BILL_" + id;
      onNodeClick(id);
    }
  }, [handleTrace, onNodeClick]);

  const elements = graphData?.elements || { nodes: [], edges: [] };

  return (
    <div className="dashboard-root">
      <header className="topbar">
        <div>
          <div className="title-row">
            <h1>{title}</h1>
            {viewMode === "detail" && (
              <button className="btn btn-secondary back-btn" onClick={loadOverview}>
                ← Back to Overview
              </button>
            )}
          </div>
          <p className="muted">
            Order-to-Cash Graph Dashboard | API: <code>{API_BASE_URL}</code>
          </p>
        </div>
        <div className="stats">
          <div className="stat-card">
            <span>Nodes</span>
            <strong>{graphData?.total_nodes ?? "-"}</strong>
          </div>
          <div className="stat-card">
            <span>Edges</span>
            <strong>{graphData?.total_edges ?? "-"}</strong>
          </div>
        </div>
      </header>

      <main className="dashboard-layout">
        <section className={`panel graph-panel ${viewMode}`}>
          {loadingGraph && (
            <div className="loading-overlay">
              <div className="spinner"></div>
              <p>Loading graph...</p>
            </div>
          )}
          
          {loadingExpand && <p className="status-toast">Expanding neighbors...</p>}
          {graphError && <p className="error banner">{graphError}</p>}
          
          {!loadingGraph && !graphError && viewMode === "overview" && (
            <OverviewGraph elements={elements} onTypeClick={onTypeClick} />
          )}
          
          {!loadingGraph && !graphError && viewMode === "detail" && (
            <GraphView elements={elements} onNodeClick={onNodeClick} />
          )}
        </section>

        <section className="side-panels">
          <QueryPanel onChatResponse={handleChatResponse} />
          {viewMode === "detail" && (
            <NodeDetailsPanel nodePayload={nodeData} loading={loadingNode} error={nodeError} />
          )}
        </section>
      </main>
    </div>
  );
}

