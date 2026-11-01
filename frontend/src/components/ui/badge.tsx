import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium whitespace-nowrap [&_svg]:size-3",
  {
    variants: {
      variant: {
        default: "bg-primary/15 text-primary",
        success: "bg-success/15 text-success",
        warning: "bg-warning/20 text-warning",
        danger: "bg-danger/15 text-danger",
        muted: "bg-muted text-muted-foreground",
        outline: "border border-border text-muted-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export function statusVariant(status: string): VariantProps<typeof badgeVariants>["variant"] {
  const s = status.toLowerCase();
  if (["active", "approved", "closed", "renewed", "low", "verified"].includes(s)) return "success";
  if (["expiring", "under review", "assessment", "medium", "pending"].includes(s)) return "warning";
  if (["lapsed", "rejected", "high"].includes(s)) return "danger";
  return "default";
}
