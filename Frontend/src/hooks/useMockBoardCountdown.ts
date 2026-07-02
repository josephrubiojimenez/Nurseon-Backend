import { useEffect, useState } from 'react';
import { loadPersistedState, savePersistedState } from '../utils/persistence';

export interface MockExamCountdownState {
    status: 'running' | 'break';
    timeRemaining: number;  // seconds
}

export function useMockBoardCountdown(): MockExamCountdownState | null {
    const [state, setState] = useState<MockExamCountdownState | null>(() => {
        // Load persisted state on mount
        const status = loadPersistedState<'selection' | 'running' | 'break' | 'deferred_lock'>(
            'mockExam.examStatus', 
            'selection'
        );
        const phaseEndTs = loadPersistedState<number>('mockExam.phaseEndTimestamp', 0);
        
        if (status === 'running' || status === 'break') {
            const timeRemaining = Math.max(0, Math.ceil((phaseEndTs - Date.now()) / 1000));
            return { status, timeRemaining };
        }
        return null;
    });

    useEffect(() => {
        if (!state) return;

        const interval = setInterval(() => {
            setState(prev => {
                if (!prev) return null;
                
                const newTime = Math.max(0, prev.timeRemaining - 1);
                
                if (newTime === 0) {
                    // Countdown finished
                    savePersistedState('mockExam.examStatus', 'selection');
                    savePersistedState('mockExam.phaseEndTimestamp', 0);
                    return null;
                }
                
                return { ...prev, timeRemaining: newTime };
            });
        }, 1000);

        return () => clearInterval(interval);
    }, [state]);

    return state;
}

export function formatCountdownTime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
}