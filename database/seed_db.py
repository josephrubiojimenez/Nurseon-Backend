from firebase import db

NURSING_DOCUMENTS = [
  {
    "id": "doc_031",
    "title": "Add",
    "category": "Fundamentals",
    "readTime": "10 mins (estimated)",
    "description": "Learn proper techniques for assessing temperature, pulse, respiration, blood pressure, and oxygen saturation.",
    "publishDate": "June 22, 2026",
    "content": [
      { "type": "paragraph", "text": "Vital signs are key clinical indicators of a patient's health status, including temperature, pulse, respiratory rate, and blood pressure. Nurses are responsible for obtaining baseline measurements upon admission and at regular intervals throughout care. Any deviation from established normal ranges must be documented and reported promptly to the healthcare team. Consistent and accurate monitoring forms the foundation of safe, effective nursing practice." },
      { "type": "paragraph", "text": "Temperature reflects the body's ability to regulate heat production and loss. Normal oral temperature in adults ranges from 36.1°C to 37.2°C (97°F to 99°F), with slight variations by route and time of day. Fever (pyrexia) is defined as a temperature above 38°C (100.4°F) and may signal infection, inflammation, or other systemic conditions. Nurses must select the most appropriate route — oral, axillary, rectal, or tympanic — based on the patient's age, condition, and level of cooperation." },
      { "type": "paragraph", "text": "Pulse assessment involves evaluating rate, rhythm, and quality at accessible arterial sites such as the radial, carotid, or apical locations. A normal adult heart rate ranges from 60 to 100 beats per minute; values outside this range are termed bradycardia or tachycardia. Irregular rhythms, such as those found in atrial fibrillation, require an apical-radial comparison and prompt clinical escalation. Peripheral pulses also offer information about circulatory adequacy and potential vascular compromise." },
      { "type": "paragraph", "text": "Respiratory rate is among the most sensitive early indicators of clinical deterioration and is frequently undertriaged in busy clinical settings. Normal adult respirations are 12 to 20 breaths per minute, and rates outside this range may indicate hypoxia, acidosis, anxiety, or medication effects. The nurse should observe the depth, rhythm, and effort of breathing alongside the rate for a complete respiratory picture. Any use of accessory muscles, nasal flaring, or paradoxical chest movement warrants urgent further assessment." },
      { "type": "paragraph", "text": "Blood pressure reflects the force of blood against arterial walls during cardiac contraction (systole) and relaxation (diastole). Normal adult blood pressure is considered less than 120/80 mmHg according to current evidence-based guidelines. The 2025 AHA/ACC hypertension guidelines maintain a diagnostic and treatment threshold of 130/80 mmHg, emphasizing earlier and more intensive blood pressure control to reduce cardiovascular events, stroke, and heart failure. Nurses must ensure proper cuff sizing, patient positioning, and bilateral comparison for accurate and reproducible results." },
      { "type": "paragraph", "text": "Oxygen saturation (SpO₂) is measured non-invasively via pulse oximetry and reflects the percentage of hemoglobin bound with oxygen. Normal SpO₂ in healthy adults ranges from 95% to 100%; readings below 90% require immediate intervention. Positive attitudes toward assessing vital signs are essential in ensuring quality assessments and recognizing patients' declining conditions. Nurses should correlate SpO₂ findings with the patient's clinical presentation, breathing effort, and history, since factors such as anemia, poor perfusion, and nail polish can affect oximeter accuracy." }
    ],
    "sources": [
      { "id": "1", "text": "Potter, P.A., Perry, A.G., Stockert, P.A., Hall, A., & Ostendorf, W.R. (2025). Fundamentals of Nursing (11th ed.). Elsevier." },
      { "id": "2", "text": "Alshehry, A.S. (2024). Attitude toward vital signs monitoring and its predictors among clinical nurses in Saudi Arabia. Frontiers in Public Health. DOI: 10.3389/fpubh.2024.1454851" },
      { "id": "3", "text": "Shahiri, T.S., & Gélinas, C. (2023). The validity of vital signs for pain assessment in critically ill adults. Pain Management Nursing, 24(3), 318–328." }
    ]
  }
]

def seed_data():
    for doc in NURSING_DOCUMENTS:
        db.collection("nursing_documents").document(doc["id"]).set(doc)
        print(f"Uploaded: {doc['title']}")

if __name__ == "__main__":
    seed_data()