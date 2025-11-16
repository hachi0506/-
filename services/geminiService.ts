
import { GoogleGenAI, Type } from "@google/genai";
import type { Player, GameSuggestion, GamePrompt } from "../types";

const API_KEY = process.env.API_KEY;
if (!API_KEY) {
  throw new Error("API_KEY environment variable is not set.");
}

const ai = new GoogleGenAI({ apiKey: API_KEY });

const parseJsonResponse = <T,>(text: string): T | null => {
  try {
    const cleanedText = text.replace(/```json/g, "").replace(/```/g, "").trim();
    return JSON.parse(cleanedText) as T;
  } catch (error) {
    console.error("Failed to parse JSON response:", error);
    console.error("Original text:", text);
    return null;
  }
};

export const suggestGames = async (): Promise<GameSuggestion[]> => {
  const prompt = `
あなたはパーティーを最高に盛り上げるゲームプランナーです。これから日本の飲み会で遊ぶための、創造的で面白い飲みゲームのアイデアを3つ提案してください。誰でもすぐに理解できて、準備が不要なゲームを選んでください。

回答は必ず以下のJSON形式のオブジェクトのみでお願いします。説明文などは不要です。
`;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            games: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  name: { type: Type.STRING, description: "ゲームの日本語名" },
                  description: { type: Type.STRING, description: "ゲームのルールと流れがわかる簡単な説明（100文字以内）" },
                  type: { type: Type.STRING, description: "ゲームの種類を識別するユニークな英語のID（例: 'never_ever', 'kings_cup_modern', 'topic_challenge'）" }
                },
                 required: ["name", "description", "type"],
              }
            }
          },
          required: ["games"],
        }
      }
    });

    const parsed = parseJsonResponse<{ games: GameSuggestion[] }>(response.text);
    if (parsed && parsed.games) {
      return parsed.games;
    }
    throw new Error("Failed to parse game suggestions from API.");
  } catch (error) {
    console.error("Error suggesting games:", error);
    throw new Error("ゲームの提案を取得できませんでした。");
  }
};

export const generateGamePrompt = async (gameType: string, players: Player[]): Promise<GamePrompt> => {
  let prompt: string;
  let responseSchema: any;
  const playerNames = players.map(p => p.name);

  switch (gameType) {
    case 'never_ever':
      prompt = `「今まで一度もやったことがない」ゲームのお題を一つ生成してください。少し個人的で、面白い暴露話が聞けそうなお題が望ましいです。`;
      responseSchema = {
        type: Type.OBJECT,
        properties: {
          prompt: { type: Type.STRING, description: "「〜したことがない人、飲んで！」という形式の文章" }
        },
        required: ["prompt"],
      };
      break;
    case 'kings_cup_modern':
      prompt = `モダンな王様ゲームの命令を一つ生成してください。参加者リストは [${playerNames.join(', ')}] です。この中からランダムに1人または2人を選び、面白くて少し恥ずかしいけど、場の空気を悪くしない楽しい命令を作成してください。`;
      responseSchema = {
        type: Type.OBJECT,
        properties: {
          command: { type: Type.STRING, description: "命令文（例：「王様の命令は絶対！ {targetPlayer1} は {targetPlayer2} のモノマネをする」）" },
          targetPlayer1: { type: Type.STRING, description: "命令を受けるプレイヤー1の名前" },
          targetPlayer2: { type: Type.STRING, description: "命令に関連するプレイヤー2の名前（いない場合はnull）" }
        },
        required: ["command", "targetPlayer1"],
      };
      break;
    case 'topic_challenge':
      prompt = `参加者が盛り上がるような面白いトークテーマを一つと、そのテーマについて話す人を一人指名してください。参加者リストは [${playerNames.join(', ')}] です。テーマは誰もが話しやすいものにしてください。`;
      responseSchema = {
        type: Type.OBJECT,
        properties: {
          prompt: { type: Type.STRING, description: "「{topic}」について、{targetPlayer}さんが熱く語ります！" },
          topic: { type: Type.STRING, description: "トークテーマ" },
          targetPlayer: { type: Type.STRING, description: "話すプレイヤーの名前" }
        },
        required: ["prompt", "topic", "targetPlayer"],
      };
      break;
    default:
       prompt = `「${gameType}」というルールのゲームをします。参加者は[${playerNames.join(', ')}]です。このゲームの次のターンのお題を生成してください。`;
       responseSchema = {
        type: Type.OBJECT,
        properties: {
          prompt: { type: Type.STRING, description: "ゲームの進行を示すプロンプト" },
          targetPlayer: { type: Type.STRING, description: "お題の対象となるプレイヤー" }
        },
        required: ["prompt"],
      };
  }

  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema
      }
    });

    const parsed = parseJsonResponse<GamePrompt>(response.text);
    if (parsed) {
      return parsed;
    }
    throw new Error("Failed to parse game prompt from API.");
  } catch (error) {
    console.error("Error generating game prompt:", error);
    throw new Error("次のお題を取得できませんでした。");
  }
};
