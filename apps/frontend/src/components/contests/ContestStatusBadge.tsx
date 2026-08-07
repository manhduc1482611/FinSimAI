/** ContestStatusBadge — nhãn trạng thái contest (draft/active/ended). */
import { Badge, type BadgeVariant } from "@/components/common/Badge";
import { statusLabel } from "@/utils/contest";

const STATUS_VARIANT: Record<string, BadgeVariant> = {
  draft: "neutral",
  active: "success",
  ended: "danger",
};

export function ContestStatusBadge({ status }: { status: string }) {
  const variant: BadgeVariant = STATUS_VARIANT[status] ?? "neutral";
  return <Badge variant={variant}>{statusLabel(status)}</Badge>;
}
