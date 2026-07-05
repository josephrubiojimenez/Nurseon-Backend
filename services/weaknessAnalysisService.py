import logging
from typing import List, Dict
from database.firebase import db
import re

logger = logging.getLogger("weakness_analysis")

SUBJECT_KEYWORDS = {
    "Medical-Surgical": [
        "medical", "surgical", "surgery", "disease", "pathology", 
        "diagnosis", "treatment", "intervention"
    ],
    "Maternal & Child": [
        "obstetric", "pregnancy", "maternal", "postpartum", "pediatric",
        "infant", "newborn", "childbirth"
    ],
    "Community Health": [
        "community", "public health", "epidemic", "prevention", "hygiene",
        "sanitation", "disease control"
    ],
    "Psychiatric": [
        "psychiatric", "mental", "psychology", "behavioral", "depression",
        "anxiety", "schizophrenia", "bipolar"
    ],
    "Pharmacology": [
        "drug", "medication", "pharmacology", "dosage", "interaction",
        "side effect", "contraindication", "toxicity"
    ],
    "Nursing Care": [
        "nursing", "care plan", "intervention", "assessment", "evaluation",
        "hygiene", "comfort", "safety"
    ]
}

def extract_subject_from_content(question: str, rationale: str) -> str:
    """
    Extract subject area from question and rationale text.
    Returns most likely subject based on keyword matching.
    """
    combined_text = f"{question} {rationale}".lower()
    
    # Count keyword matches for each subject
    subject_scores = {}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined_text)
        if score > 0:
            subject_scores[subject] = score
    
    if subject_scores:
        return max(subject_scores, key=subject_scores.get)
    
    return "General Knowledge"


def analyze_user_weaknesses(uid: str, num_exams: int = 3) -> Dict:
    """
    Analyze weak areas from recent exam attempts.
    Returns structured weakness data with recommendations.
    """
    try:
        exams_ref = db.collection("users").document(uid).collection("mock_exams")
        recent_exams = list(
            exams_ref.order_by("submitted_at", direction="DESCENDING").limit(num_exams).stream()
        )
        
        if not recent_exams:
            return {
                "weaknesses": [],
                "recommendation": "Complete your first mock exam to see your weak areas."
            }
        
        subject_performance = {}
        
        # Process each exam
        for exam_doc in recent_exams:
            exam_data = exam_doc.to_dict() or {}
            if exam_data.get("status") != "submitted":
                continue
            
            breakdown = exam_data.get("evaluation_breakdown", {})
            
            for q_id, result in breakdown.items():
                is_correct = result.get("is_correct", False)
                question = result.get("question", "")
                rationale = result.get("rationale", "")
                
                # Extract subject from question/rationale
                subject = extract_subject_from_content(question, rationale)
                
                if subject not in subject_performance:
                    subject_performance[subject] = {
                        "correct": 0,
                        "total": 0,
                        "questions": []
                    }
                
                subject_performance[subject]["total"] += 1
                if is_correct:
                    subject_performance[subject]["correct"] += 1
                else:
                    # Track missed questions for recommendations
                    subject_performance[subject]["questions"].append({
                        "text": question[:100],  # First 100 chars
                        "rationale": rationale[:200]
                    })
        
        # Calculate performance and priority
        weaknesses = []
        for subject, data in subject_performance.items():
            total = data["total"]
            correct = data["correct"]
            percent = (correct / total * 100) if total > 0 else 0
            
            if percent < 75:  # Less than 75% is weak
                if percent < 60:
                    priority = "critical"
                elif percent < 70:
                    priority = "medium"
                else:
                    priority = "low"
                
                weaknesses.append({
                    "subject": subject,
                    "percent": round(percent, 1),
                    "priority": priority,
                    "totalQuestions": total,
                    "correctAnswers": correct
                })
        
        # Sort by percent (lowest first)
        weaknesses.sort(key=lambda x: x["percent"])
        
        # Generate personalized recommendation
        recommendation = generate_recommendation(weaknesses)
        
        logger.info(f"Analyzed weaknesses for {uid}: {len(weaknesses)} weak areas found")
        
        return {
            "weaknesses": weaknesses[:5],  # Top 5 weak areas
            "recommendation": recommendation
        }
    
    except Exception as e:
        logger.error(f"Weakness analysis failed for {uid}: {str(e)}", exc_info=True)
        return {
            "weaknesses": [],
            "recommendation": "Unable to analyze weaknesses at this time."
        }


def generate_recommendation(weaknesses: List[Dict]) -> str:

    if not weaknesses:
        return "Excellent performance! Continue reviewing all topics to maintain and strengthen your knowledge."
    
    if len(weaknesses) == 1:
        top_weak = weaknesses[0]
        return (
            f"Focus on {top_weak['subject']} ({top_weak['percent']}% accuracy). "
            f"Review clinical concepts and practice more questions in this area before your next exam."
        )
    
    top_two = weaknesses[:2]
    subjects = " and ".join([w["subject"] for w in top_two])
    
    return (
        f"Priority areas: {subjects}. "
        f"These topics need more attention. Review the clinical concepts, "
        f"rationales for missed questions, and practice similar question types."
    )