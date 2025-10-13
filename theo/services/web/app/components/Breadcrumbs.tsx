import Link from "next/link";
import type { ReactNode } from "react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  icon?: ReactNode;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
}

export default function Breadcrumbs({ items, className }: BreadcrumbsProps): JSX.Element {
  if (items.length === 0) {
    return <></>;
  }

  const lastIndex = items.length - 1;

  return (
    <nav aria-label="Breadcrumb" className={className ? `breadcrumbs ${className}` : "breadcrumbs"}>
      <ol className="breadcrumbs__list">
        {items.map((item, index) => {
          const isCurrent = index === lastIndex;
          const content = (
            <>
              {item.icon ? <span className="breadcrumbs__icon">{item.icon}</span> : null}
              <span>{item.label}</span>
            </>
          );

          let node: JSX.Element;
          if (isCurrent) {
            node = (
              <span className="breadcrumbs__current" aria-current="page">
                {content}
              </span>
            );
          } else if (item.href) {
            node = (
              <Link href={item.href} className="breadcrumbs__link">
                {content}
              </Link>
            );
          } else {
            node = <span className="breadcrumbs__label">{content}</span>;
          }

          return (
            <li key={`${item.href ?? item.label}-${index}`} className="breadcrumbs__item">
              {node}
              {!isCurrent ? <span className="breadcrumbs__separator" aria-hidden="true">/</span> : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
