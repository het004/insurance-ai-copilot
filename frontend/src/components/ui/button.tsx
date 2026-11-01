import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
    "focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98] " +
    "[&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-brand text-white shadow-lg shadow-primary/25 hover:brightness-110",
        secondary: "border border-primary/40 bg-card-solid text-primary hover:bg-primary/5",
        outline: "border border-border bg-transparent hover:bg-muted",
        ghost: "hover:bg-muted",
        destructive: "bg-danger text-white hover:brightness-110",
      },
      size: {
        default: "h-11 px-5",
        sm: "h-9 px-3 text-xs",
        lg: "h-13 px-7 text-base",
        icon: "size-11",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";

export { buttonVariants };
