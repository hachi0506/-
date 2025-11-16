import React from 'react';
import type { GamePrompt, Player, GameSuggestion } from '../types';
import { Button } from './common/Button';
import { Card } from './common/Card';
import { PlayerTag } from './common/PlayerTag';
import { Loader } from './common/Loader';
import { playClickSound } from '../services/audioService';

interface GameplayScreenProps {
  game: GameSuggestion;
  players: Player[];
  prompt: GamePrompt | null;
  isLoading: boolean;
  onNextPrompt: () => void;
  onEndGame: () => void;
}

export const GameplayScreen: React.FC<GameplayScreenProps> = ({ game, players, prompt, isLoading, onNextPrompt, onEndGame }) => {

  const handleNextClick = () => {
    playClickSound();
    onNextPrompt();
  }
  
  const renderPrompt = () => {
    if (!prompt) return <p className="text-gray-500">準備中...</p>;

    const highlightPlayer = (text: string | undefined) => {
        if (!text) return text;
        let highlightedText: React.ReactNode[] = [text];
        players.forEach(player => {
            const regex = new RegExp(`(${player.name})`, 'g');
            highlightedText = highlightedText.flatMap(part => {
                if (typeof part !== 'string') return [part];
                return part.split(regex).map((subPart, i) => 
                    i % 2 === 1 ? <PlayerTag key={`${player.id}-${i}`} name={subPart} size="lg" className="inline-block mx-1 align-middle" /> : subPart
                );
            });
        });
        return highlightedText;
    };

    const baseTextStyle = "text-2xl md:text-3xl font-bold text-center leading-relaxed text-gray-800 animate-fade-in-up";
    const promptKey = JSON.stringify(prompt);

    if (prompt.prompt) {
      return <p key={promptKey} className={baseTextStyle}>{highlightPlayer(prompt.prompt)}</p>;
    }
    if (prompt.command) {
      return <p key={promptKey} className={baseTextStyle}>{highlightPlayer(prompt.command)}</p>;
    }
    return <p className="text-gray-500">次のお題を待っててね...</p>;
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-between p-4">
      <header className="w-full max-w-4xl mx-auto flex justify-between items-center p-4">
        <div>
          <h1 className="text-2xl font-bold text-pink-600">{game.name}</h1>
          <div className="flex flex-wrap gap-2 mt-2">
            {players.map(p => <PlayerTag key={p.id} name={p.name} size="sm" />)}
          </div>
        </div>
        <Button onClick={onEndGame} variant="secondary">ゲーム終了</Button>
      </header>

      <main className="flex-grow flex items-center justify-center w-full">
        <Card className="w-full max-w-2xl min-h-[300px] flex items-center justify-center p-8">
          {isLoading ? <Loader text="次のお題考えてるよ！"/> : renderPrompt()}
        </Card>
      </main>

      <footer className="w-full max-w-4xl mx-auto p-4">
        <Button onClick={handleNextClick} disabled={isLoading} className="w-full text-xl animate-pulse">
          次のターン！
        </Button>
      </footer>
    </div>
  );
};