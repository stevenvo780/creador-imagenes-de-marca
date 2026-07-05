/**
 * Card — superficie editorial elevada con borde sutil.
 * Padding: 'sm' | 'md' | 'lg' | 'none'
 */
import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactNode;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  elevated?: boolean;
  style?: React.CSSProperties;
  className?: string;
  as?: React.ElementType;
}

const paddingMap: Record<NonNullable<CardProps['padding']>, string> = {
  none: '0',
  sm:   'var(--space-3)',
  md:   'var(--space-4) var(--space-5)',
  lg:   'var(--space-6) var(--space-8)',
};

export function Card({
  children,
  padding = 'md',
  elevated = false,
  style,
  className,
  as: Tag = 'div',
  ...props
}: CardProps) {
  const computedStyle: React.CSSProperties = {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--r-lg)',
    padding: paddingMap[padding],
    boxShadow: elevated ? 'var(--shadow-2)' : 'var(--shadow-1)',
    ...style,
  };

  return (
    <Tag style={computedStyle} className={className} {...props}>
      {children}
    </Tag>
  );
}
