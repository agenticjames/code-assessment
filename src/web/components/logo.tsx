/**
 * Biggy brand mark — an original wordmark/logo in BigPanda's house style
 * (electric blue → cyan gradient). Not a reproduction of BigPanda's logo.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect width="32" height="32" rx="8" fill="url(#biggy-mark)" />
      <path
        d="M5 18 H10 L12.2 11 L15.2 23 L17.6 16.5 L19 18 H27"
        stroke="#ffffff"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <defs>
        <linearGradient
          id="biggy-mark"
          x1="0"
          y1="0"
          x2="32"
          y2="32"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#026CE5" />
          <stop offset="1" stopColor="#14BFF4" />
        </linearGradient>
      </defs>
    </svg>
  );
}
