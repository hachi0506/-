import React from 'react';

interface LoaderProps {
  text?: string;
}

export const Loader: React.FC<LoaderProps> = ({ text = "AIが考えてるよ...🤔" }) => {
  return (
    <div className="flex flex-col items-center justify-center space-y-4 text-center">
      <div className="w-12 h-12 border-4 border-t-pink-500 border-pink-200 rounded-full animate-spin"></div>
      <p className="text-lg font-semibold text-gray-700">{text}</p>
    </div>
  );
};