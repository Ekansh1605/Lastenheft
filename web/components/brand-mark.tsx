/**
 * Lastenheft brand mark — "LS" in bold emerald on a stone-800 rounded square.
 * Renders inline as React SVG so it inherits color preferences and scales sharply.
 */
export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width={size}
      height={size}
      className="flex-shrink-0"
      aria-hidden
    >
      <rect width="32" height="32" rx="6" fill="#292524" />
      <text
        x="16"
        y="16"
        textAnchor="middle"
        dominantBaseline="central"
        fontFamily="-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
        fontSize="13"
        fontWeight="800"
        fill="#10b981"
        letterSpacing="-0.5"
      >
        LS
      </text>
    </svg>
  );
}
