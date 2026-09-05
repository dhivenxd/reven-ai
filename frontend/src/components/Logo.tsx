interface LogoProps {
  variant?: 'mark' | 'wordmark' | 'full';
  size?: 'sm' | 'md' | 'lg';
}

export function Logo({ variant = 'full', size = 'md' }: LogoProps) {
  const sizeMap = { sm: 24, md: 32, lg: 48 };
  const s = sizeMap[size];

  if (variant === 'mark') {
    return (
      <svg
        width={s}
        height={s}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        {/* Background */}
        <rect width="32" height="32" rx="6" fill="#0F0F0F" />
        {/* Feedback loop mark: circle with gap + arrow */}
        <circle
          cx="16"
          cy="16"
          r="10"
          stroke="#F5F4F0"
          strokeWidth="1.5"
          strokeDasharray="50 13"
          strokeDashoffset="-8"
          strokeLinecap="round"
        />
        {/* Arrow head pointing right — completing the loop */}
        <path
          d="M24.5 11.5L28 16L24.5 20.5"
          stroke="#00C896"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  if (variant === 'wordmark') {
    return (
      <span style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        fontWeight: 500,
        color: 'var(--reven-text)',
        letterSpacing: '-0.01em',
      }}>
        reven
      </span>
    );
  }

  // full — mark + wordmark
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
      <svg
        width={s}
        height={s}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <rect width="32" height="32" rx="6" fill="#0F0F0F" />
        <circle
          cx="16"
          cy="16"
          r="10"
          stroke="#F5F4F0"
          strokeWidth="1.5"
          strokeDasharray="50 13"
          strokeDashoffset="-8"
          strokeLinecap="round"
        />
        <path
          d="M24.5 11.5L28 16L24.5 20.5"
          stroke="#00C896"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span style={{
        fontFamily: 'var(--font-ui)',
        fontSize: 'var(--text-sm)',
        fontWeight: 500,
        color: 'var(--reven-text)',
        letterSpacing: '-0.01em',
      }}>
        reven
      </span>
    </div>
  );
}
