import React from "react";

interface Props {
  text: string;
}

/**
 * Safely parses inline markdown tokens (**bold**, *italic*, `code`, [link](url))
 * into standard React JSX nodes without using dangerouslySetInnerHTML.
 */
function renderInline(text: string): React.ReactNode[] {
  // Regex matches: **bold**, *italic*, `code`, [link text](url)
  const tokenRegex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];
    const key = `${match.index}-${token.length}`;

    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(<strong key={key}>{renderInline(token.slice(2, -2))}</strong>);
    } else if (token.startsWith("*") && token.endsWith("*")) {
      parts.push(<em key={key}>{renderInline(token.slice(1, -1))}</em>);
    } else if (token.startsWith("`") && token.endsWith("`")) {
      parts.push(<code key={key} className="inline-code">{token.slice(1, -1)}</code>);
    } else if (token.startsWith("[") && token.includes("](") && token.endsWith(")")) {
      const closeBracket = token.indexOf("](");
      const label = token.slice(1, closeBracket);
      const url = token.slice(closeBracket + 2, -1);
      const isSafeUrl = /^(https?:\/\/|mailto:)/i.test(url.trim());
      if (isSafeUrl) {
        parts.push(
          <a key={key} href={url.trim()} target="_blank" rel="noopener noreferrer">
            {renderInline(label)}
          </a>
        );
      } else {
        parts.push(label);
      }
    } else {
      parts.push(token);
    }

    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

function parseTableRow(line: string): string[] {
  const trimmed = line.trim();
  const inner = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  return inner.split("|").map((c) => c.trim());
}

function isTableSeparator(line: string): boolean {
  const cells = parseTableRow(line);
  return cells.length > 0 && cells.every((c) => /^:?-+:?$/.test(c));
}

/**
 * Safe React Markdown Renderer.
 * Parses headers, tables, bullet lists, numbered lists, blockquotes, and paragraphs.
 * Fully XSS-safe: Uses React JSX elements only, never dangerouslySetInnerHTML.
 */
export default function SafeRecommendationRenderer({ text }: Props) {
  if (!text || !text.trim()) {
    return <p className="recommendation-empty">No recommendation provided.</p>;
  }

  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // 1. Skip blank lines
    if (!trimmed) {
      i++;
      continue;
    }

    // 2. Markdown Table Detection
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }

      if (tableLines.length >= 2 && isTableSeparator(tableLines[1])) {
        const headers = parseTableRow(tableLines[0]);
        const bodyRows = tableLines.slice(2).map(parseTableRow);

        elements.push(
          <div key={`table-${i}`} className="recommendation-table-wrap">
            <table className="recommendation-table">
              <thead>
                <tr>
                  {headers.map((h, colIdx) => (
                    <th key={colIdx}>{renderInline(h)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bodyRows.map((row, rowIdx) => (
                  <tr key={rowIdx}>
                    {row.map((cell, colIdx) => (
                      <td key={colIdx}>{renderInline(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        continue;
      }
    }

    // 3. Headings
    if (trimmed.startsWith("### ")) {
      elements.push(<h4 key={`h3-${i}`} className="rec-heading rec-h3">{renderInline(trimmed.slice(4))}</h4>);
      i++;
      continue;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(<h3 key={`h2-${i}`} className="rec-heading rec-h2">{renderInline(trimmed.slice(3))}</h3>);
      i++;
      continue;
    }
    if (trimmed.startsWith("# ")) {
      elements.push(<h2 key={`h1-${i}`} className="rec-heading rec-h1">{renderInline(trimmed.slice(2))}</h2>);
      i++;
      continue;
    }

    // 4. Blockquote
    if (trimmed.startsWith("> ")) {
      elements.push(
        <blockquote key={`quote-${i}`} className="rec-blockquote">
          {renderInline(trimmed.slice(2))}
        </blockquote>
      );
      i++;
      continue;
    }

    // 5. Unordered List (- or *)
    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""));
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} className="rec-list rec-ul">
          {items.map((item, itemIdx) => (
            <li key={itemIdx}>{renderInline(item)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // 6. Ordered List (1. 2.)
    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i++;
      }
      elements.push(
        <ol key={`ol-${i}`} className="rec-list rec-ol">
          {items.map((item, itemIdx) => (
            <li key={itemIdx}>{renderInline(item)}</li>
          ))}
        </ol>
      );
      continue;
    }

    // 7. Regular paragraph
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("#") &&
      !lines[i].trim().startsWith("|") &&
      !lines[i].trim().startsWith("> ") &&
      !/^[-*]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim())
    ) {
      paraLines.push(lines[i].trim());
      i++;
    }
    elements.push(
      <p key={`p-${i}`} className="rec-paragraph">
        {renderInline(paraLines.join(" "))}
      </p>
    );
  }

  return <div className="recommendation-content">{elements}</div>;
}
