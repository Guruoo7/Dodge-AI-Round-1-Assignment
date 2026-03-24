const isProd = import.meta.env.PROD;
const defaultBaseUrl = isProd 
  ? "https://dodge-ai-round-1-assignment.onrender.com" 
  : "http://127.0.0.1:8000";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || defaultBaseUrl;

async function request(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text || response.statusText}`);
  }
  return response.json();
}

export async function getGraph() {
  return request("/graph");
}

export async function getInitialGraph(maxNodes = 100) {
  return request(`/graph/initial?max_nodes=${encodeURIComponent(maxNodes)}`);
}

export async function getNeighbors(nodeId, maxNewNodes = 40) {
  return request(
    `/graph/neighbors/${encodeURIComponent(nodeId)}?max_new_nodes=${encodeURIComponent(maxNewNodes)}`
  );
}

export async function getNode(nodeId) {
  return request(`/node/${encodeURIComponent(nodeId)}`);
}

export async function getOverviewGraph() {
  return request('/graph/overview');
}

export async function traceSalesOrder(salesOrder) {
  return request(`/graph/trace/sales-order/${encodeURIComponent(salesOrder)}`);
}

export async function traceBillingDocument(billingDocument) {
  return request(`/trace/${encodeURIComponent(billingDocument)}`);
}

export async function getBrokenFlows(limit = 20) {
  return request(`/graph/trace/broken-flows?limit=${encodeURIComponent(limit)}`);
}

export async function chatQuery(query) {
  const response = await fetch(`${API_BASE_URL}/chat/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Chat API Error: ${text || response.statusText}`);
  }
  return response.json();
}

export { API_BASE_URL };

