import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Cloudscape-friendly Markdown renderer for assistant chat bubbles.
 * - GFM tables/strikethrough/task-lists enabled.
 * - Tight margins so bubbles don't get airy.
 * - Code blocks render with a subtle background.
 */
export default function Markdown({ source }: { source: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ node: _node, ...props }) => (
            <p style={{ margin: "0 0 8px" }} {...props} />
          ),
          ul: ({ node: _node, ...props }) => (
            <ul style={{ margin: "0 0 8px 18px" }} {...props} />
          ),
          ol: ({ node: _node, ...props }) => (
            <ol style={{ margin: "0 0 8px 18px" }} {...props} />
          ),
          li: ({ node: _node, ...props }) => (
            <li style={{ margin: "2px 0" }} {...props} />
          ),
          h1: ({ node: _node, ...props }) => (
            <h2 style={{ margin: "12px 0 6px", fontSize: 18 }} {...props} />
          ),
          h2: ({ node: _node, ...props }) => (
            <h3 style={{ margin: "12px 0 6px", fontSize: 16 }} {...props} />
          ),
          h3: ({ node: _node, ...props }) => (
            <h4 style={{ margin: "10px 0 4px", fontSize: 14 }} {...props} />
          ),
          code: ({ node: _node, className, children, ...props }) => {
            const isBlock = (className ?? "").startsWith("language-");
            return isBlock ? (
              <pre
                style={{
                  background: "#f4f4f4",
                  borderRadius: 4,
                  padding: 8,
                  fontSize: 12,
                  overflow: "auto",
                  margin: "6px 0",
                }}
              >
                <code {...props}>{children}</code>
              </pre>
            ) : (
              <code
                style={{
                  background: "#f4f4f4",
                  borderRadius: 3,
                  padding: "0 4px",
                  fontSize: 12,
                }}
                {...props}
              >
                {children}
              </code>
            );
          },
          table: ({ node: _node, ...props }) => (
            <div style={{ overflowX: "auto", margin: "6px 0" }}>
              <table
                style={{
                  borderCollapse: "collapse",
                  fontSize: 12,
                  width: "100%",
                }}
                {...props}
              />
            </div>
          ),
          th: ({ node: _node, ...props }) => (
            <th
              style={{
                border: "1px solid #d1d5db",
                padding: "4px 8px",
                background: "#f4f4f4",
                textAlign: "left",
              }}
              {...props}
            />
          ),
          td: ({ node: _node, ...props }) => (
            <td
              style={{
                border: "1px solid #d1d5db",
                padding: "4px 8px",
                verticalAlign: "top",
              }}
              {...props}
            />
          ),
          blockquote: ({ node: _node, ...props }) => (
            <blockquote
              style={{
                borderLeft: "3px solid #b0b7be",
                margin: "6px 0",
                padding: "2px 10px",
                color: "#414d5c",
              }}
              {...props}
            />
          ),
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
