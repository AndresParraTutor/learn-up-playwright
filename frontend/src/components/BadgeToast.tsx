import type { Badge } from "../api/types";

export default function BadgeToast({ badges }: { badges: Badge[] }) {
  if (badges.length === 0) return null;
  return (
    <div className="toast" role="status">
      {badges.map((badge) => (
        <p key={badge.code}>
          {badge.icon} <strong>{badge.name}</strong>
        </p>
      ))}
    </div>
  );
}
