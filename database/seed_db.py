from firebase import db

NURSING_DOCUMENTS = [
  {
  "id": "doc_036",
  "title": "Nursing Ethics and Ethical Principles",
  "category": "Pro-Practice",
  "readTime": "12 mins (estimated)",
  "description": "Understand the ethical principles that guide professional nursing practice and patient-centered care.",
  "publishDate": "June 29, 2026",
  "content": [
    { "type": "paragraph", "text": "Nursing ethics refers to the moral principles and standards that guide nurses in providing safe, compassionate, and professional care. Ethical nursing practice promotes patient dignity, autonomy, and advocacy while ensuring accountability and integrity in all healthcare interactions. Nurses frequently encounter ethical dilemmas that require careful analysis, clinical judgment, and adherence to professional codes of ethics." },
    { "type": "paragraph", "text": "Autonomy is the ethical principle that recognizes a patient's right to make informed decisions regarding their own healthcare. Nurses must respect patients' values, beliefs, and preferences, even when these choices differ from the healthcare provider's recommendations. Supporting informed consent and ensuring that patients receive complete and understandable information are essential responsibilities of the nurse." },
    { "type": "paragraph", "text": "Beneficence refers to the obligation to act in the best interest of the patient by promoting health, preventing harm, and maximizing benefits. Nurses demonstrate beneficence by providing evidence-based interventions, advocating for appropriate treatment, and ensuring patient comfort and safety. Every nursing action should aim to improve patient outcomes and overall well-being." },
    { "type": "paragraph", "text": "Nonmaleficence, commonly summarized as 'do no harm,' requires nurses to avoid causing unnecessary injury or suffering. This principle includes preventing medication errors, maintaining competence, following safety protocols, and recognizing situations that place patients at risk. Nurses must carefully weigh potential benefits and risks before implementing interventions." },
    { "type": "paragraph", "text": "Justice involves fairness and equality in the distribution of healthcare resources and treatment. Nurses must provide equitable care regardless of a patient's age, gender, socioeconomic status, ethnicity, or cultural background. Ethical nursing practice demands that all patients receive respectful and unbiased care." },
    { "type": "paragraph", "text": "Fidelity and veracity are essential professional values in nursing. Fidelity refers to keeping commitments and maintaining trust, whereas veracity emphasizes honesty and truthfulness in all patient interactions. Nurses who uphold these principles strengthen therapeutic relationships and promote ethical healthcare environments." }
  ],
  "sources": [
    { "id": "1", "text": "American Nurses Association. (2025). Code of Ethics for Nurses with Interpretive Statements. ANA Publishing." },
    { "id": "2", "text": "Butts, J.B., & Rich, K.L. (2024). Nursing Ethics: Across the Curriculum and Into Practice (6th ed.). Jones & Bartlett Learning." },
    { "id": "3", "text": "Grace, P.J. (2024). Nursing Ethics and Professional Responsibility in Advanced Practice (4th ed.). Jones & Bartlett Learning." }
  ]
},
]

def seed_data():
    for doc in NURSING_DOCUMENTS:
        db.collection("nursing_documents").document(doc["id"]).set(doc)
        print(f"Uploaded: {doc['title']}")

if __name__ == "__main__":
    seed_data()