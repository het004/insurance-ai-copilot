import { cn } from "@/lib/utils";

export function PageHeader({
  title, subtitle, icon, actions, className,
}: { title: string; subtitle?: string; icon?: React.ReactNode; actions?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="flex items-center gap-3">
        {icon && <span className="grid size-11 place-items-center rounded-2xl bg-primary/12 text-primary">{icon}</span>}
        <div>
          <h1 className="text-xl font-semibold tracking-tight md:text-2xl">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>}
        </div>
      </div>
      {actions}
    </div>
  );
}

export function PageContainer({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-6xl px-4 py-5 md:px-8 md:py-8", className)}>{children}</div>;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-muted", className)} />;
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="font-medium underline">Retry</button>}
    </div>
  );
}
