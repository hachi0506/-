
export interface Player {
  id: number;
  name: string;
}

export interface GameSuggestion {
  name: string;
  description: string;
  type: string;
}

export interface GamePrompt {
  prompt?: string;
  command?: string;
  targetPlayer?: string;
  targetPlayer1?: string;
  targetPlayer2?: string;
  topic?: string;
}

export enum AppState {
  Welcome,
  SelectingGame,
  PlayingGame,
}
