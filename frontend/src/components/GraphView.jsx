import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

const NODE_COLORS = {
  Customer: "#2563eb",
  Address: "#0891b2",
  SalesOrder: "#7c3aed",
  SalesOrderItem: "#9333ea",
  ScheduleLine: "#a855f7",
  Delivery: "#0d9488",
  DeliveryItem: "#14b8a6",
  BillingDocument: "#f59e0b",
  BillingDocumentItem: "#f97316",
  JournalEntry: "#4f46e5",
  Payment: "#16a34a",
  Product: "#dc2626",
  Plant: "#475569",
  Unknown: "#6b7280"
};

function cytoscapeStyle() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "background-color": "data(color)",
        color: "#111827",
        "font-size": 10,
        "text-wrap": "wrap",
        "text-max-width": 90,
        "text-valign": "bottom",
        "text-margin-y": 8,
        width: 22,
        height: 22,
        "border-color": "#ffffff",
        "border-width": 1.2
      }
    },
    {
      selector: "edge",
      style: {
        width: 1.4,
        "line-color": "#9ca3af",
        "target-arrow-color": "#9ca3af",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        label: "data(label)",
        color: "#6b7280",
        "font-size": 8,
        "text-rotation": "autorotate",
        "text-background-color": "#ffffff",
        "text-background-opacity": 0.65,
        "text-background-padding": 1
      }
    },
    {
      selector: "node:selected",
      style: {
        "overlay-color": "#3b82f6",
        "overlay-opacity": 0.2,
        "border-width": 3,
        "border-color": "#3b82f6"
      }
    },
    {
      selector: "node.expanded",
      style: {
        "border-width": 2,
        "border-style": "dashed",
        "border-color": "#4b5563"
      }
    }
  ];
}

export default function GraphView({ elements, onNodeClick }) {
  const containerRef = useRef(null);
  const graphRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const nodes = (elements?.nodes || []).map((n) => {
      const nodeType = n?.data?.node_type || "Unknown";
      return {
        ...n,
        data: {
          ...n.data,
          color: NODE_COLORS[nodeType] || NODE_COLORS.Unknown
        }
      };
    });
    const edges = elements?.edges || [];

    // Initialize Cytoscape once
    if (!graphRef.current) {
      const cy = cytoscape({
        container: containerRef.current,
        elements: [...nodes, ...edges],
        layout: {
          name: "cose",
          animate: true,
          animationDuration: 300,
          padding: 24,
          idealEdgeLength: 110,
          nodeRepulsion: 3200
        },
        minZoom: 0.1,
        maxZoom: 2.5,
        style: cytoscapeStyle()
      });

      cy.on("tap", "node", (event) => {
        const id = event.target.id();
        event.target.addClass('expanded');
        onNodeClick?.(id);
      });

      graphRef.current = cy;
    } else {
      // Incremental update
      const cy = graphRef.current;
      
      // Track existing IDs
      const existingNodes = new Set(cy.nodes().map(n => n.id()));
      const existingEdges = new Set(cy.edges().map(e => e.id()));

      // Identify new elements
      const newNodes = nodes.filter(n => !existingNodes.has(n.data.id));
      const newEdges = edges.filter(e => !existingEdges.has(e.data.id));
      
      if (newNodes.length > 0 || newEdges.length > 0) {
        cy.add([...newNodes, ...newEdges]);
        
        // Re-run layout just on the new stuff and its neighborhood if possible, 
        // or just re-run cose with randomization turned off for existing nodes
        cy.layout({
          name: 'cose',
          randomize: false,
          animate: true,
          animationDuration: 500,
          fit: false,
          padding: 30,
          nodeRepulsion: 3200,
          idealEdgeLength: 110,
        }).run();
      }
      
      // Also check if we need to remove elements (e.g. going from trace back to initial)
      const targetNodeIds = new Set(nodes.map(n => n.data.id));
      const targetEdgeIds = new Set(edges.map(e => e.data.id));
      
      const nodesToRemove = cy.nodes().filter(n => !targetNodeIds.has(n.id()));
      const edgesToRemove = cy.edges().filter(e => !targetEdgeIds.has(e.id()));
      
      if (nodesToRemove.length > 0 || edgesToRemove.length > 0) {
        cy.remove(nodesToRemove.union(edgesToRemove));
        cy.layout({
          name: 'cose',
          randomize: false,
          animate: true,
          animationDuration: 500
        }).run();
      }
    }

    return () => {
      // Don't destroy on every render, only on full unmount
    };
  }, [elements, onNodeClick]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (graphRef.current) {
        graphRef.current.destroy();
        graphRef.current = null;
      }
    };
  }, []);

  return <div className="graph-canvas" ref={containerRef} />;
}

