import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
  className?: string;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  className = '',
  ...props
}) => {
  const baseClasses = 'px-6 py-3 font-bold rounded-full shadow-lg transform transition-all duration-200 focus:outline-none focus:ring-4';
  
  const variantClasses = {
    primary: 'bg-gradient-to-br from-pink-500 to-orange-400 text-white hover:saturate-150 active:scale-95 focus:ring-pink-300 shadow-pink-500/30',
    secondary: 'bg-white text-pink-500 border-2 border-pink-400 hover:bg-pink-50 active:scale-95 focus:ring-pink-300 shadow-pink-500/20',
  };

  const disabledClasses = 'disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed disabled:shadow-none disabled:scale-100 disabled:saturate-50 disabled:border-transparent';

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${disabledClasses} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
};