import type { HTMLAttributes, ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react'

interface TableProps extends HTMLAttributes<HTMLTableElement> { children: ReactNode }
function Table({ className = '', children, ...rest }: TableProps) {
  return (
    <table {...rest} className={`w-full text-sm text-ink ${className}`}>
      {children}
    </table>
  )
}

function Head({ children, className = '', ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead {...rest} className={`text-ink-faint ${className}`}>{children}</thead>
}

function Body({ children, className = '', ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...rest} className={className}>{children}</tbody>
}

function Row({ children, className = '', ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr {...rest} className={`border-b border-divider last:border-b-0 ${className}`}>
      {children}
    </tr>
  )
}

interface CellProps extends Omit<TdHTMLAttributes<HTMLTableCellElement>, 'children'> {
  numeric?: boolean
  children: ReactNode
}
function Cell({ numeric = false, className = '', children, ...rest }: CellProps) {
  const align = numeric ? 'text-right tnum-mono' : ''
  return (
    <td {...rest} className={`py-3 px-3 align-baseline ${align} ${className}`}>
      {children}
    </td>
  )
}

interface HeadCellProps extends Omit<ThHTMLAttributes<HTMLTableCellElement>, 'children'> {
  numeric?: boolean
  children: ReactNode
}
function HeadCell({ numeric = false, className = '', children, ...rest }: HeadCellProps) {
  const align = numeric ? 'text-right' : 'text-left'
  return (
    <th
      {...rest}
      className={`py-2 px-3 text-[10px] uppercase tracking-[0.18em] font-semibold ${align} ${className}`}
    >
      {children}
    </th>
  )
}

Table.Head = Head
Table.Body = Body
Table.Row = Row
Table.Cell = Cell
Table.HeadCell = HeadCell

export { Table as DataTable }
