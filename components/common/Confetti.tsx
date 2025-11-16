import React from 'react';

const CONFETTI_COUNT = 100;
const COLORS = ['#f472b6', '#fb923c', '#facc15', '#4ade80', '#60a5fa'];

const ConfettiPiece: React.FC<{ index: number }> = ({ index }) => {
  const style: React.CSSProperties = {
    left: `${Math.random() * 100}vw`,
    backgroundColor: COLORS[Math.floor(Math.random() * COLORS.length)],
    animationDelay: `${Math.random() * 2}s`,
    animationDuration: `${3 + Math.random() * 2}s`,
    transform: `rotate(${Math.random() * 360}deg)`,
  };
  return <div className="confetti" style={style}></div>;
};

export const Confetti: React.FC = () => {
  return (
    <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-50 overflow-hidden">
      {Array.from({ length: CONFETTI_COUNT }).map((_, i) => (
        <ConfettiPiece key={i} index={i} />
      ))}
    </div>
  );
};
