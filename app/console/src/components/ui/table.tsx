import * as React from "react"
import { Info } from "lucide-react"

import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

const STICKY_HEAD = "[&_th]:sticky [&_th]:top-0 [&_th]:z-10 [&_th]:bg-card [&_th]:shadow-[inset_0_-1px_0_theme(colors.dbb.warm)]"

const Table = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement> & { wrapperClassName?: string }
>(({ className, wrapperClassName, ...props }, ref) => (
  <div className={cn("relative w-full overflow-x-auto", wrapperClassName)}>
    <table
      ref={ref}
      className={cn("w-full caption-bottom text-sm", className)}
      {...props}
    />
  </div>
))
Table.displayName = "Table"

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead
    ref={ref}
    className={cn("text-left text-dbb-muted [&_tr]:border-b [&_tr]:border-dbb-warm", className)}
    {...props}
  />
))
TableHeader.displayName = "TableHeader"

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("[&_tr:last-child]:border-0", className)}
    {...props}
  />
))
TableBody.displayName = "TableBody"

const TableFooter = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tfoot
    ref={ref}
    className={cn(
      "border-t border-dbb-warm bg-dbb-sand/50 font-medium [&>tr]:last:border-b-0",
      className
    )}
    {...props}
  />
))
TableFooter.displayName = "TableFooter"

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "border-b border-dbb-warm/30 transition-colors data-[state=selected]:bg-dbb-sand",
      className
    )}
    {...props}
  />
))
TableRow.displayName = "TableRow"

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement> & { hint?: string }
>(({ className, hint, children, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "whitespace-nowrap pb-2 pr-4 text-left align-middle font-medium text-dbb-muted",
      className
    )}
    {...props}
  >
    {children}
    {hint ? (
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={hint}
            data-testid="hint"
            className="ml-1 inline-flex align-[-2px] text-dbb-muted/60 hover:text-dbb-charcoal focus-visible:text-dbb-charcoal focus-visible:outline-none"
          >
            <Info size={12} strokeWidth={2} />
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          {hint}
        </TooltipContent>
      </Tooltip>
    ) : null}
  </th>
))
TableHead.displayName = "TableHead"

const TableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn("py-2 pr-4 align-middle text-dbb-muted break-words", className)}
    {...props}
  />
))
TableCell.displayName = "TableCell"

const TableCaption = React.forwardRef<
  HTMLTableCaptionElement,
  React.HTMLAttributes<HTMLTableCaptionElement>
>(({ className, ...props }, ref) => (
  <caption
    ref={ref}
    className={cn("mt-4 text-sm text-dbb-muted", className)}
    {...props}
  />
))
TableCaption.displayName = "TableCaption"

export {
  STICKY_HEAD,
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
