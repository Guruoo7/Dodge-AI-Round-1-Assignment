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

const ICONS = {
  Customer: "\uf0c0", // users
  SalesOrder: "\uf07a", // shopping-cart
  Delivery: "\uf0d1", // truck
  BillingDocument: "\uf15c", // file-alt
  Payment: "\uf0d6", // money-bill-alt
  Product: "\uf466", // box
  Plant: "\uf275", // industry
};

function cytoscapeStyle() {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        "background-color": "data(color)",
        color: "#111827",
        "font-size": 14,
        "font-weight": "bold",
        "text-wrap": "wrap",
        "text-max-width": 120,
        "text-valign": "center",
        "text-halign": "center",
        width: 80,
        height: 80,
        "border-color": "#ffffff",
        "border-width": 3,
        "shadow-blur": 10,
        "shadow-color": "rgba(0,0,0,0.15)",
        "shadow-opacity": 1,
        "transition-property": "background-color, shadow-blur, border-width, width, height",
        "transition-duration": 200,
        "color": "#ffffff",
        "text-outline-color": "data(color)",
        "text-outline-width": 2,
      }
    },
    {
      selector: "edge",
      style: {
        width: 3,
        "line-color": "#cbd5e1",
        "target-arrow-color": "#cbd5e1",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        label: "data(label)",
        color: "#475569",
        "font-size": 11,
        "font-weight": "600",
        "text-rotation": "autorotate",
        "text-background-color": "#ffffff",
        "text-background-opacity": 0.9,
        "text-background-padding": 4,
        "text-background-shape": "roundrectangle",
        "text-border-color": "#cbd5e1",
        "text-border-width": 1,
        "text-border-opacity": 1,
        "transition-property": "line-color, target-arrow-color, width",
        "transition-duration": 200,
      }
    },
    {
      selector: "node:hover",
      style: {
        "shadow-color": "data(color)",
        "shadow-blur": 20,
        "border-width": 4,
        "cursor": "pointer"
      }
    },
    {
      selector: "edge:hover",
      style: {
        "line-color": "#94a3b8",
        "target-arrow-color": "#94a3b8",
        "width": 5,
        "cursor": "pointer"
      }
    }
  ];
}

export default function OverviewGraph({ elements, onTypeClick }) {
  const containerRef = useRef(null);
  const graphRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !elements) return undefined;

    if (graphRef.current) {
      graphRef.current.destroy();
      graphRef.current = null;
    }

    const nodes = (elements.nodes || []).map((n) => {
      const nodeType = n.data.node_type || "Unknown";
      
      return {
        ...n,
        data: {
          ...n.data,
          color: NODE_COLORS[nodeType] || NODE_COLORS.Unknown,
        }
      };
    });
    const edges = elements.edges || [];

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      layout: {
        name: "cose",
        animate: true,
        animationDuration: 500,
        padding: 50,
        nodeRepulsion: 8000,
        idealEdgeLength: 150,
        edgeElasticity: 100,
        gravity: 0.2,
      },
      minZoom: 0.2,
      maxZoom: 2,
      style: cytoscapeStyle(),
      boxSelectionEnabled: false,
      autoungrabify: false,
    });

    cy.on("mouseover", "node, edge", (e) => {
      e.target.addClass('hover');
    });

    cy.on("mouseout", "node, edge", (e) => {
      e.target.removeClass('hover');
    });

    cy.on("tap", "node", (event) => {
      const type = event.target.data("node_type");
      onTypeClick?.(type);
    });

    graphRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [elements, onTypeClick]);

  return (
    <div className="overview-container">
      <div className="graph-canvas" ref={containerRef} style={{ height: "65vh" }} />
      <div className="overview-legend">
        <h4>Business Entities</h4>
        <div className="legend-items">
          {Object.entries(NODE_COLORS).filter(([type]) => type !== 'Unknown').map(([type, color]) => (
            <div key={type} className="legend-item" onClick={() => onTypeClick?.(type)}>
              <span className="color-dot" style={{ backgroundColor: color }}></span>
              <span>{type.replace(/([A-Z])/g, ' $1').trim()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
