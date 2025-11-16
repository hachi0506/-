import React from 'react';
import type { GameSuggestion } from '../types';
import { Card } from './common/Card';
import { playClickSound } from '../services/audioService';

interface GameSelectionScreenProps {
  suggestions: GameSuggestion[];
  onSelectGame: (game: GameSuggestion) => void;
}

export const GameSelectionScreen: React.FC<GameSelectionScreenProps> = ({ suggestions, onSelectGame }) => {
  const handleSelect = (game: GameSuggestion) => {
    playClickSound();
    onSelectGame(game);
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto text-center">
        <h2 className="text-3xl font-bold mb-2 text-gray-800">どのゲームで遊ぶ？</h2>
        <p className="text-gray-600 mb-8">AIにおすすめ聞いてみたよ！下の３つから選んでね👇</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {suggestions.map((game, index) => (
            <Card
              key={index}
              className="text-left flex flex-col"
              onClick={() => handleSelect(game)}
            >
              <h3 className="text-xl font-bold text-pink-600 mb-2">{game.name}</h3>
              <p className="text-gray-700 flex-grow">{game.description}</p>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};