import { API_BASE_URL } from '../src/config/api.config';
import { loadPersistedState, savePersistedState } from '../src/utils/persistence';

export interface UserProgress {
    quizzesAnswered: number;
    totalQuizzes: number;
    caseStudiesCompleted: number;
    totalCaseStudies: number;
    mockExamsTaken: number;
    totalMockExams: number;
    overallAccuracy: number;
    latestBoardScore: number;
    overallBoardScore: number;
    studyStreak: number;
    timeSpentHours: number;
    weaknesses: Weakness[];
    weaknessRecommendation: string;
}

export interface Weakness {
    subject: string;
    percent: number;
    priority: 'critical' | 'medium' | 'low';
}

const CACHE_KEY = 'progressData';
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export async function fetchUserProgress(uid: string, forceRefresh: boolean = false): Promise<UserProgress> {
    try {
        // Check cache first
        if (!forceRefresh) {
            // Explicitly added "| null" inside the generic argument to accept a null fallback
            const cached = loadPersistedState<{
                data: UserProgress;
                timestamp: number;
            } | null>(CACHE_KEY, null);
            
            if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
                return cached.data;
            }
        }

        const response = await fetch(`${API_BASE_URL}/api/progress/${uid}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data: UserProgress = await response.json();
        
        // Cache result
        savePersistedState(CACHE_KEY, {
            data,
            timestamp: Date.now()
        });

        return data;
    } catch (error) {
        console.error('Progress fetch failed:', error);
        
        // Return safe defaults, not hardcoded values
        return {
            quizzesAnswered: 0,
            totalQuizzes: 50,
            caseStudiesCompleted: 0,
            totalCaseStudies: 20,
            mockExamsTaken: 0,
            totalMockExams: 5,
            overallAccuracy: 0,
            latestBoardScore: 0,
            overallBoardScore: 0,
            studyStreak: 0,
            timeSpentHours: 0,
            weaknesses: [],
            weaknessRecommendation: 'Data unavailable'
        };
    }
}

export function invalidateProgressCache(): void {
    savePersistedState(CACHE_KEY, null);
}