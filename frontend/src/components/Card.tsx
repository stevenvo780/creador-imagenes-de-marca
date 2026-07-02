/**
 * Card — superficie elevada con borde y sombra sutil.
 * Padding: 'sm' | 'md' | 'lg' | 'none'
 */
import React from 'react';

export interface CardProps {
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
}: CardProps) {
  const computedStyle: React.CSSProperties = {
    background: 'var(--white)',
    border: '1px solid var(--line)',
    borderRadius: 'var(--radius-lg)',
    padding: paddingMap[padding],
    boxShadow: elevated ? 'var(--shadow-md)' : 'var(--shadow-sm)',
    ...style,
  };

  return (
    <Tag style={computedStyle} className={className}>
      {children}
    </Tag>
  );
}
