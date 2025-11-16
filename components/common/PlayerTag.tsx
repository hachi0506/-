import React from 'react';

interface PlayerTagProps {
  name: string;
  className?: string;
  onRemove?: () => void;
  size?: 'sm' | 'md' | 'lg';
}

const colorClasses = [
  'bg-pink-300 text-pink-800 border border-pink-400',
  'bg-yellow-300 text-yellow-800 border border-yellow-400',
  'bg-sky-300 text-sky-800 border border-sky-400',
  'bg-lime-300 text-lime-800 border border-lime-400',
  'bg-violet-300 text-violet-800 border border-violet-400',
  'bg-orange-300 text-orange-800 border border-orange-400',
];

export const PlayerTag: React.FC<PlayerTagProps> = ({ name, className = '', onRemove, size = 'md' }) => {
  const colorClass = React.useMemo(() => colorClasses[Math.floor(Math.random() * colorClasses.length)], []);

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1.5 text-sm',
    lg: 'px-4 py-2 text-base'
  }

  return (
    <div className={`flex items-center justify-between rounded-full font-bold shadow-sm ${sizeClasses[size]} ${colorClass} ${className}`}>
      <span>{name}</span>
      {onRemove && (
        <button
          onClick={onRemove}
          className="ml-2 w-5 h-5 flex items-center justify-center bg-black/20 rounded-full text-white/80 hover:bg-black/40 transition-colors"
        >
          &times;
        </button>
      )}
    </div>
  );
};