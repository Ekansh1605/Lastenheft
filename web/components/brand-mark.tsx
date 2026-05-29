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
      {/* Warm-grey backdrop with subtle inner glow — sits well on the
          warm-dark interface without being flat black. */}
      <rect width="32" height="32" rx="7" fill="#2a241c" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="6.5" fill="none" stroke="#3a332a" strokeWidth="1" />
      <text
        x="16"
        y="16.5"
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
