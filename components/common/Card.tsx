import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export const Card: React.FC<CardProps> = ({ children, className = '', onClick }) => {
  const clickableClasses = onClick ? 'cursor-pointer transform hover:scale-105 hover:shadow-2xl hover:shadow-pink-400/40 transition-all duration-300' : '';
  
  return (
    <div
      className={`bg-white/60 backdrop-blur-md border border-pink-200 rounded-2xl shadow-lg p-6 ${clickableClasses} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
};