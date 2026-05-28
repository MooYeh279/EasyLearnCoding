import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

interface Props {
  content: string;
}

const DESIGN = {
  primary: '#5b5feb',
  success: '#10b981',
  text: '#1e1e24',
  textSecondary: '#6b7280',
  border: '#e8e8ed',
  borderRadius: 10,
  codeBg: '#1e1e2e',
  codeBorder: '#2d2d3f',
  inlineCodeBg: '#f3f4f6',
  inlineCodeColor: '#e11d48',
  headerBg: '#f8f9fb',
  blockquoteBg: '#f8f9fd',
  headingBorder: '#ececf2',
} as const;

export default function MarkdownRenderer({ content }: Props) {
  const components = useMemo(
    () => ({
      h1({ children, ...props }: any) {
        return (
          <h1
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: DESIGN.text,
              margin: '28px 0 16px',
              paddingBottom: 10,
              borderBottom: `2px solid ${DESIGN.headingBorder}`,
              lineHeight: 1.3,
              letterSpacing: '-0.02em',
            }}
            {...props}
          >
            {children}
          </h1>
        );
      },
      h2({ children, ...props }: any) {
        return (
          <h2
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: DESIGN.text,
              margin: '24px 0 14px',
              paddingBottom: 8,
              borderBottom: `2px solid ${DESIGN.headingBorder}`,
              lineHeight: 1.3,
              letterSpacing: '-0.01em',
            }}
            {...props}
          >
            {children}
          </h2>
        );
      },
      h3({ children, ...props }: any) {
        return (
          <h3
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: '#27273a',
              margin: '20px 0 10px',
              lineHeight: 1.35,
            }}
            {...props}
          >
            {children}
          </h3>
        );
      },
      h4({ children, ...props }: any) {
        return (
          <h4
            style={{
              fontSize: 16,
              fontWeight: 600,
              color: DESIGN.textSecondary,
              margin: '18px 0 8px',
              lineHeight: 1.4,
            }}
            {...props}
          >
            {children}
          </h4>
        );
      },
      p({ children, ...props }: any) {
        return (
          <p
            style={{
              margin: '1.2em 0',
              lineHeight: 1.8,
              color: DESIGN.text,
              fontSize: 15,
            }}
            {...props}
          >
            {children}
          </p>
        );
      },
      ul({ children, ...props }: any) {
        return (
          <ul
            style={{
              margin: '12px 0',
              paddingLeft: 24,
              listStylePosition: 'outside',
              lineHeight: 1.8,
              color: DESIGN.text,
              fontSize: 15,
            }}
            {...props}
          >
            {children}
          </ul>
        );
      },
      ol({ children, ...props }: any) {
        return (
          <ol
            style={{
              margin: '12px 0',
              paddingLeft: 24,
              listStylePosition: 'outside',
              lineHeight: 1.8,
              color: DESIGN.text,
              fontSize: 15,
            }}
            {...props}
          >
            {children}
          </ol>
        );
      },
      li({ children, ...props }: any) {
        return (
          <li
            style={{
              margin: '4px 0',
              color: DESIGN.text,
            }}
            {...props}
          >
            {children}
          </li>
        );
      },
      blockquote({ children, ...props }: any) {
        return (
          <blockquote
            style={{
              margin: '16px 0',
              padding: '14px 20px',
              borderLeft: `4px solid ${DESIGN.primary}`,
              background: DESIGN.blockquoteBg,
              borderRadius: `0 ${DESIGN.borderRadius}px ${DESIGN.borderRadius}px 0`,
              fontStyle: 'italic',
              color: '#4a4a5c',
              fontSize: 15,
              lineHeight: 1.7,
            }}
            {...props}
          >
            {children}
          </blockquote>
        );
      },
      a({ children, href, ...props }: any) {
        return (
          <a
            href={href}
            style={{
              color: DESIGN.primary,
              textDecoration: 'none',
              fontWeight: 500,
              borderBottom: '1.5px solid transparent',
              transition: 'border-color 0.15s ease',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.borderBottomColor =
                DESIGN.primary;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.borderBottomColor =
                'transparent';
            }}
            {...props}
          >
            {children}
          </a>
        );
      },
      img({ src, alt, ...props }: any) {
        return (
          <img
            src={src}
            alt={alt}
            style={{
              maxWidth: '100%',
              borderRadius: DESIGN.borderRadius,
              margin: '16px 0',
            }}
            {...props}
          />
        );
      },
      code({ className, children, ...props }: any) {
        const match = /language-(\w+)/.exec(className || '');
        const codeStr = String(children).replace(/\n$/, '');
        if (match) {
          return (
            <div
              style={{
                borderRadius: DESIGN.borderRadius,
                overflow: 'hidden',
                border: `1px solid ${DESIGN.codeBorder}`,
                margin: '16px 0',
                background: DESIGN.codeBg,
              }}
            >
              {/* macOS-style window bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '10px 16px',
                  background: '#1a1a28',
                  borderBottom: `1px solid ${DESIGN.codeBorder}`,
                }}
              >
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: '#ff5f56',
                    display: 'inline-block',
                  }}
                />
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: '#ffbd2e',
                    display: 'inline-block',
                  }}
                />
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: '#27ca40',
                    display: 'inline-block',
                  }}
                />
                <span
                  style={{
                    marginLeft: 'auto',
                    fontSize: 11,
                    fontWeight: 500,
                    color: '#7c7c9a',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    fontFamily:
                      'ui-sans-serif, system-ui, -apple-system, sans-serif',
                  }}
                >
                  {match[1]}
                </span>
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: '16px 20px',
                  overflow: 'auto',
                  background: 'transparent',
                }}
              >
                <code
                  className={className}
                  style={{
                    fontFamily:
                      "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
                    fontSize: 13.5,
                    lineHeight: 1.65,
                    color: '#e2e8f0',
                  }}
                  {...props}
                >
                  {codeStr}
                </code>
              </pre>
            </div>
          );
        }
        return (
          <code
            className={className}
            style={{
              background: DESIGN.inlineCodeBg,
              color: DESIGN.inlineCodeColor,
              padding: '2px 6px',
              borderRadius: 5,
              fontFamily:
                "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
              fontSize: '0.88em',
            }}
            {...props}
          >
            {children}
          </code>
        );
      },
      table({ children, ...props }: any) {
        return (
          <div
            style={{
              overflow: 'auto',
              margin: '14px 0',
              borderRadius: DESIGN.borderRadius,
              border: `1px solid ${DESIGN.border}`,
            }}
          >
            <table
              style={{
                borderCollapse: 'collapse',
                width: '100%',
                fontSize: 14,
              }}
              {...props}
            >
              {children}
            </table>
          </div>
        );
      },
      thead({ children, ...props }: any) {
        return (
          <thead style={{ background: DESIGN.headerBg }} {...props}>
            {children}
          </thead>
        );
      },
      th({ children, ...props }: any) {
        return (
          <th
            style={{
              borderBottom: `2px solid ${DESIGN.border}`,
              borderRight: `1px solid ${DESIGN.border}`,
              padding: '10px 14px',
              textAlign: 'left',
              fontWeight: 600,
              fontSize: 13,
              color: DESIGN.text,
            }}
            {...props}
          >
            {children}
          </th>
        );
      },
      td({ children, ...props }: any) {
        return (
          <td
            style={{
              borderBottom: `1px solid ${DESIGN.border}`,
              borderRight: `1px solid ${DESIGN.border}`,
              padding: '9px 14px',
              textAlign: 'left',
              color: DESIGN.text,
            }}
            {...props}
          >
            {children}
          </td>
        );
      },
      tr({ children, index, ...props }: any) {
        const isEven = typeof index === 'number' && index % 2 === 1;
        return (
          <tr
            style={{
              background: isEven ? '#fafbfc' : 'transparent',
            }}
            {...props}
          >
            {children}
          </tr>
        );
      },
      hr(_props: any) {
        return (
          <hr
            style={{
              border: 'none',
              borderTop: `1px solid ${DESIGN.border}`,
              margin: '24px 0',
            }}
          />
        );
      },
      strong({ children, ...props }: any) {
        return (
          <strong style={{ fontWeight: 600, color: '#14141a' }} {...props}>
            {children}
          </strong>
        );
      },
      em({ children, ...props }: any) {
        return (
          <em style={{ fontStyle: 'italic', color: '#3a3a4a' }} {...props}>
            {children}
          </em>
        );
      },
    }),
    [],
  );

  return (
    <div style={{ lineHeight: 1.8, color: DESIGN.text }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
