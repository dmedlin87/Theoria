'use client';

import { createContext, useContext, type ReactNode } from 'react';

export type StudyMode = 'neutral' | 'apologetic' | 'skeptical';

export const ModeContext = createContext<StudyMode>('neutral');

export function useMode(): StudyMode {
  return useContext(ModeContext);
}

interface ModeProviderProps {
  value: StudyMode;
  children: ReactNode;
}

export function ModeProvider({ value, children }: ModeProviderProps) {
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

