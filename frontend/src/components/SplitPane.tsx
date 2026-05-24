import { useState, useCallback, useRef, useEffect, type ReactNode } from 'react';

interface Props {
  children: [ReactNode, ReactNode];
  initialLeft?: string;   // e.g. "44%" or "260px"
  minLeft?: string;       // minimum left-panel width
  minRight?: string;      // minimum right-panel width
  style?: React.CSSProperties;
}

export default function SplitPane({ children, initialLeft = '44%', minLeft = '220px', minRight = '280px', style }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [leftWidth, setLeftWidth] = useState(initialLeft);
  const dragging = useRef(false);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const total = rect.width;
      const pct = (x / total) * 100;
      // Clamp: enforce min via pixel check
      const minLeftPx = parsePx(minLeft, total);
      const minRightPx = parsePx(minRight, total);
      const clampedPct = Math.max(minLeftPx / total * 100, Math.min(pct, (total - minRightPx) / total * 100));
      setLeftWidth(`${clampedPct}%`);
    };
    const onMouseUp = () => {
      if (dragging.current) {
        dragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, [minLeft, minRight]);

  return (
    <div ref={containerRef} style={{ display: 'flex', overflow: 'hidden', ...style }}>
      <div style={{ width: leftWidth, flexShrink: 0, overflow: 'hidden' }}>
        {children[0]}
      </div>
      <div
        onMouseDown={onMouseDown}
        style={{
          width: 6,
          flexShrink: 0,
          cursor: 'col-resize',
          background: 'transparent',
          transition: 'background 0.15s',
          zIndex: 10,
        }}
        onMouseEnter={(e) => { (e.target as HTMLElement).style.background = 'rgba(91,95,235,0.25)'; }}
        onMouseLeave={(e) => {
          if (!dragging.current) (e.target as HTMLElement).style.background = 'transparent';
        }}
      />
      <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
        {children[1]}
      </div>
    </div>
  );
}

function parsePx(val: string, total: number): number {
  if (val.endsWith('%')) return total * parseFloat(val) / 100;
  if (val.endsWith('px')) return parseFloat(val);
  return 0;
}
