import type { ReactNode } from "react";

export function ActionButton({
  children,
  icon,
  primary,
  onClick,
  disabled
}: {
  children: ReactNode;
  icon?: ReactNode;
  primary?: boolean;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      className={primary ? "action-button primary" : "action-button"}
      onClick={onClick}
      disabled={disabled}
    >
      {icon}
      {children}
    </button>
  );
}
