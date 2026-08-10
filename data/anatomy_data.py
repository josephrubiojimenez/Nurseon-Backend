# Backend/data/anatomy_data.py
# Curated educational content for the NurseOn Anatomy & Clinical Learning Lab.

# Each structure may carry:
#   id, name, category, type, location, region, layer, function,
#   key_facts, anatomical_landmarks, clinical_relevance, related_structures

SKELETAL_SYSTEM = {
    "id": "skeletal_system",
    "name": "Skeletal System",
    "description": "Provides structural support, protects vital organs, and acts as levers for movement.",
    "structures": [
        {
            "id": "femur",
            "name": "Femur",
            "category": "Skeletal System",
            "type": "Long bone",
            "location": "Thigh",
            "region": "thigh",
            "layer": "skeletal",
            "function": "Supports body weight, provides structural support for movement, and serves as an attachment point for muscles.",
            "key_facts": [
                "The longest and strongest bone in the human body.",
                "Composed of a head, neck, shaft, and distal condyles.",
                "Forms the hip joint proximally and the knee joint distally."
            ],
            "anatomical_landmarks": ["Greater trochanter", "Lesser trochanter", "Linea aspera", "Medial and lateral epicondyles", "Patellar surface"],
            "clinical_relevance": "Femur fractures can cause significant blood loss and are common in trauma. Understanding its anatomy is essential for assessing mobility, traction, and post-operative nursing care.",
            "related_structures": ["tibia", "patella", "hip_joint"]
        },
        {
            "id": "tibia",
            "name": "Tibia",
            "category": "Skeletal System",
            "type": "Long bone",
            "location": "Lower leg (medial side)",
            "region": "leg",
            "layer": "skeletal",
            "function": "Main weight-bearing bone of the lower leg; forms the knee and ankle joints.",
            "key_facts": ["Also called the shinbone.", "Articulates with the femur superiorly and the talus inferiorly."],
            "anatomical_landmarks": ["Tibial tuberosity", "Medial malleolus", "Anterior crest"],
            "clinical_relevance": "Prone to open fractures because it is superficial. Nurses assess circulation, sensation, and movement distal to tibial injuries.",
            "related_structures": ["femur", "patella"]
        },
        {
            "id": "patella",
            "name": "Patella",
            "category": "Skeletal System",
            "type": "Sesamoid bone",
            "location": "Anterior aspect of the knee",
            "region": "knee",
            "layer": "skeletal",
            "function": "Protects the knee joint and improves quadriceps leverage during leg extension.",
            "key_facts": ["Embedded within the quadriceps tendon.", "Articulates with the patellar surface of the femur."],
            "anatomical_landmarks": ["Apex", "Base", "Articular facets"],
            "clinical_relevance": "Dislocations are common during physical activity. Relevant for knee injury assessment and post-operative rehabilitation.",
            "related_structures": ["femur", "tibia", "quadriceps_femoris"]
        },
        {
            "id": "skull",
            "name": "Cranium (Skull)",
            "category": "Skeletal System",
            "type": "Flat/irregular bones",
            "location": "Head",
            "region": "head",
            "layer": "skeletal",
            "function": "Encloses and protects the brain; provides attachment for facial muscles.",
            "key_facts": ["Made up of cranium (8 bones) and facial skeleton (14 bones).", "Sutures unite most cranial bones."],
            "anatomical_landmarks": ["Bregma", "Lambda", "Pterion", "Foramen magnum"],
            "clinical_relevance": "Fractures can injure the brain. Nurses monitor for signs of increased intracranial pressure after head trauma.",
            "related_structures": ["brain"]
        }
    ]
}

MUSCULAR_SYSTEM = {
    "id": "muscular_system",
    "name": "Muscular System",
    "description": "Enables movement, maintains posture, and generates body heat.",
    "structures": [
        {
            "id": "quadriceps_femoris",
            "name": "Quadriceps Femoris",
            "category": "Muscular System",
            "type": "Muscle group",
            "location": "Anterior thigh",
            "region": "thigh",
            "layer": "muscular",
            "function": "Extends the knee and flexes the hip.",
            "key_facts": ["Four muscles: Rectus Femoris, Vastus Lateralis, Vastus Medialis, Vastus Intermedius.", "Inserts at the tibial tuberosity via the patellar tendon."],
            "anatomical_landmarks": ["Patellar tendon", "Tibial tuberosity", "Anterior superior iliac spine"],
            "clinical_relevance": "Essential for standing, walking, and climbing. Weakness affects ambulation; relevant to falls risk and rehabilitation nursing.",
            "related_structures": ["femur", "patella", "tibia"]
        },
        {
            "id": "gastrocnemius",
            "name": "Gastrocnemius",
            "category": "Muscular System",
            "type": "Skeletal muscle",
            "location": "Posterior calf (lower leg)",
            "region": "leg",
            "layer": "muscular",
            "function": "Plantar flexes the foot and flexes the knee; aids in walking and running.",
            "key_facts": ["Forms the bulk of the calf.", "Two heads originate from the femoral condyles."],
            "anatomical_landmarks": ["Achilles tendon", "Medial and lateral heads"],
            "clinical_relevance": "Deep vein thrombosis can present with calf tenderness. Nurses assess Homans sign cautiously and enforce DVT prophylaxis.",
            "related_structures": ["tibia", "achilles_tendon"]
        }
    ]
}

CARDIOVASCULAR_SYSTEM = {
    "id": "cardiovascular_system",
    "name": "Cardiovascular System",
    "description": "Transports blood, oxygen, nutrients, and waste products throughout the body.",
    "structures": [
        {
            "id": "heart",
            "name": "Heart",
            "category": "Cardiovascular System",
            "type": "Muscular organ (myocardium)",
            "location": "Mediastinum, between the lungs",
            "region": "chest",
            "layer": "cardiovascular",
            "function": "Pumps blood through the systemic and pulmonary circulations to perfuse all tissues.",
            "key_facts": ["Four chambers: two atria, two ventricles.", "Pumps ~5 liters of blood per minute at rest."],
            "anatomical_landmarks": ["Apex (5th intercostal space, midclavicular line)", "Base", "Sternocostal surface", "Diaphragmatic surface"],
            "clinical_relevance": "Auscultation points for heart valves are vital. Nurses monitor for heart failure, arrhythmias, and myocardial infarction.",
            "related_structures": ["aorta", "lungs"]
        },
        {
            "id": "aorta",
            "name": "Aorta",
            "category": "Cardiovascular System",
            "type": "Elastic artery",
            "location": "From the left ventricle to the abdomen",
            "region": "chest",
            "layer": "cardiovascular",
            "function": "Largest artery; distributes oxygenated blood to the systemic circulation.",
            "key_facts": ["Divided into ascending, arch, thoracic, and abdominal portions.", "Aortic root contains the aortic valve."],
            "anatomical_landmarks": ["Aortic arch", "Bifurcation into common iliac arteries"],
            "clinical_relevance": "Aortic aneurysm or dissection is life-threatening. Nurses recognize sudden severe tearing chest/back pain and hypotension.",
            "related_structures": ["heart", "common_carotid_artery"]
        },
        {
            "id": "common_carotid_artery",
            "name": "Common Carotid Artery",
            "category": "Cardiovascular System",
            "type": "Artery",
            "location": "Neck",
            "region": "neck",
            "layer": "cardiovascular",
            "function": "Supplies oxygenated blood to the head and neck.",
            "key_facts": ["Bifurcates into internal and external carotid arteries.", "Pulse can be palpated in the neck."],
            "anatomical_landmarks": ["Carotid bifurcation", "Carotid sinus", "Carotid body"],
            "clinical_relevance": "Carotid pulse is a central pulse assessed in CPR. Carotid sinus massage may affect heart rate and blood pressure.",
            "related_structures": ["aorta", "heart"]
        }
    ]
}

RESPIRATORY_SYSTEM = {
    "id": "respiratory_system",
    "name": "Respiratory System",
    "description": "Facilitates gas exchange (oxygen in, carbon dioxide out) and maintains acid-base balance.",
    "structures": [
        {
            "id": "lungs",
            "name": "Lungs",
            "category": "Respiratory System",
            "type": "Paired organ",
            "location": "Thoracic cavity (right and left)",
            "region": "chest",
            "layer": "respiratory",
            "function": "Site of gas exchange between air and blood via alveoli.",
            "key_facts": ["Right lung has 3 lobes, left lung has 2 (accommodates heart).", "Contain ~480 million alveoli."],
            "anatomical_landmarks": ["Apex", "Base", "Hilum", "Costodiaphragmatic recess"],
            "clinical_relevance": "Assess breath sounds, oxygenation (SpO2), and positioning (e.g., semi-Fowler). Relevant to pneumonia, asthma, and COPD.",
            "related_structures": ["heart", "trachea", "diaphragm"]
        },
        {
            "id": "trachea",
            "name": "Trachea",
            "category": "Respiratory System",
            "type": "Airway (cartilaginous tube)",
            "location": "Neck to mid-chest",
            "region": "neck",
            "layer": "respiratory",
            "function": "Conducts air from the larynx to the bronchi.",
            "key_facts": ["C-shaped cartilage rings keep it patent.", "Carina divides into left and right main bronchi."],
            "anatomical_landmarks": ["Carina", "Tracheal rings"],
            "clinical_relevance": "Site for endotracheal intubation and tracheostomy care; nurses maintain airway patency and suction technique.",
            "related_structures": ["lungs", "diaphragm"]
        },
        {
            "id": "diaphragm",
            "name": "Diaphragm",
            "category": "Respiratory System",
            "type": "Skeletal muscle (primary inspiratory)",
            "location": "Base of the thoracic cavity",
            "region": "abdomen",
            "layer": "respiratory",
            "function": "Main muscle of inspiration; increases thoracic volume during contraction.",
            "key_facts": ["Separates thoracic and abdominal cavities.", "Innervated by the phrenic nerve (C3-C5)."],
            "anatomical_landmarks": ["Esophageal hiatus", "Aortic hiatus", "Caval opening"],
            "clinical_relevance": "Cervical spinal injuries can paralyze the diaphragm. Nurses monitor respiratory effort in spinal cord injury and after abdominal surgery.",
            "related_structures": ["lungs", "liver"]
        }
    ]
}

DIGESTIVE_SYSTEM = {
    "id": "digestive_system",
    "name": "Digestive System",
    "description": "Breaks down food, absorbs nutrients, and eliminates waste.",
    "structures": [
        {
            "id": "stomach",
            "name": "Stomach",
            "category": "Digestive System",
            "type": "Hollow muscular organ",
            "location": "Left upper quadrant of abdomen",
            "region": "abdomen",
            "layer": "digestive",
            "function": "Stores and mechanically/chemically digests food; produces gastric acid and enzymes.",
            "key_facts": ["Regions: cardia, fundus, body, pylorus.", "Secretes hydrochloric acid and pepsin."],
            "anatomical_landmarks": ["Cardia", "Fundus", "Pyloric sphincter", "Greater and lesser curvature"],
            "clinical_relevance": "Peptic ulcer disease, gastric bleeding, and nasogastric tube placement all relate to stomach anatomy.",
            "related_structures": ["liver", "small_intestine", "esophagus"]
        },
        {
            "id": "liver",
            "name": "Liver",
            "category": "Digestive System",
            "type": "Glandular organ",
            "location": "Right upper quadrant of abdomen",
            "region": "abdomen",
            "layer": "digestive",
            "function": "Produces bile, metabolizes nutrients and drugs, stores glycogen, and detoxifies blood.",
            "key_facts": ["Largest internal organ.", "Has four lobes and dual blood supply (hepatic artery + portal vein)."],
            "anatomical_landmarks": ["Right and left lobes", "Porta hepatis", "Inferior vena cava groove"],
            "clinical_relevance": "Liver is highly vascular; protects underlying structures. Nurses assess hepatomegaly, jaundice, and liver enzyme trends.",
            "related_structures": ["stomach", "gallbladder", "diaphragm"]
        },
        {
            "id": "small_intestine",
            "name": "Small Intestine",
            "category": "Digestive System",
            "type": "Hollow muscular organ",
            "location": "Central abdomen (duodenum, jejunum, ileum)",
            "region": "abdomen",
            "layer": "digestive",
            "function": "Primary site of nutrient absorption.",
            "key_facts": ["~6 meters long.", "Contains villi and microvilli that maximize absorption."],
            "anatomical_landmarks": ["Duodenum", "Jejunum", "Ileum", "Ileocecal valve"],
            "clinical_relevance": "Bowel sounds are auscultated over quadrants representing small intestine motility. Relevant to obstruction and post-op ileus.",
            "related_structures": ["stomach", "liver", "pancreas"]
        }
    ]
}

NERVOUS_SYSTEM = {
    "id": "nervous_system",
    "name": "Nervous System",
    "description": "Rapidly coordinates and controls body functions through electrical and chemical signals.",
    "structures": [
        {
            "id": "brain",
            "name": "Brain",
            "category": "Nervous System",
            "type": "Organ",
            "location": "Cranial cavity",
            "region": "head",
            "layer": "nervous",
            "function": "Central control center for thought, sensation, movement, and regulation of vital functions.",
            "key_facts": ["Composed of cerebrum, cerebellum, and brainstem.", "Covered by meninges and cushioned by cerebrospinal fluid."],
            "anatomical_landmarks": ["Cerebrum", "Cerebellum", "Brainstem", "Ventricles"],
            "clinical_relevance": "Monitor level of consciousness, pupil reactivity, and GCS after head injury or stroke. Neurology nursing requires precise assessments.",
            "related_structures": ["skull", "spinal_cord"]
        },
        {
            "id": "spinal_cord",
            "name": "Spinal Cord",
            "category": "Nervous System",
            "type": "Nervous tissue",
            "location": "Within the vertebral canal",
            "region": "back",
            "layer": "nervous",
            "function": "Conducts sensory and motor signals between the brain and the body; coordinates reflexes.",
            "key_facts": ["Ends around L1-L2 (conus medullaris).", "Protected by vertebral column and meninges."],
            "anatomical_landmarks": ["Cervical enlargement", "Lumbar enlargement", "Conus medullaris", "Cauda equina"],
            "clinical_relevance": "Spinal cord injury requires immobilization and meticulous assessment of motor/sensory function to prevent further damage.",
            "related_structures": ["brain", "sciatic_nerve"]
        },
        {
            "id": "sciatic_nerve",
            "name": "Sciatic Nerve",
            "category": "Nervous System",
            "type": "Peripheral nerve",
            "location": "Posterior pelvis and thigh to lower leg",
            "region": "thigh",
            "layer": "nervous",
            "function": "Largest nerve; innervates much of the lower limb.",
            "key_facts": ["Formed from L4-S3 spinal roots.", "Travels through the greater sciatic foramen."],
            "anatomical_landmarks": ["Greater sciatic foramen", "Piriformis muscle relation", "Common fibular and tibial branches"],
            "clinical_relevance": "Sciatica and herniated disc cause radiating pain. Nurses assess sciatic nerve function and provide positioning and pain relief.",
            "related_structures": ["spinal_cord", "femur"]
        }
    ]
}

ANATOMY_DATA = {
    "systems": [
        SKELETAL_SYSTEM,
        MUSCULAR_SYSTEM,
        CARDIOVASCULAR_SYSTEM,
        RESPIRATORY_SYSTEM,
        DIGESTIVE_SYSTEM,
        NERVOUS_SYSTEM,
    ]
}

def get_anatomy_data():
    """Returns the entire anatomy dataset."""
    return ANATOMY_DATA

def get_system_by_id(system_id: str):
    """Returns a specific system by its ID."""
    for system in ANATOMY_DATA.get("systems", []):
        if system["id"] == system_id:
            return system
    return None

def get_structure_by_id(structure_id: str):
    """Returns a specific structure by its ID across all systems."""
    for system in ANATOMY_DATA.get("systems", []):
        for structure in system.get("structures", []):
            if structure["id"] == structure_id:
                return structure
    return None

def search_structures(query: str):
    """Searches for structures by name (case-insensitive)."""
    results = []
    query_lower = query.lower().strip()
    if not query_lower:
        return results
    for system in ANATOMY_DATA.get("systems", []):
        for structure in system.get("structures", []):
            haystack = (structure["name"] + " " + structure.get("location", "")).lower()
            if query_lower in haystack:
                results.append({
                    "id": structure["id"],
                    "name": structure["name"],
                    "category": structure["category"],
                    "type": structure["type"],
                    "location": structure["location"],
                    "region": structure.get("region")
                })
    return results

def get_related_structures(structure_ids):
    """Retrieves brief details for a list of related structure IDs."""
    related_details = []
    for struct_id in structure_ids or []:
        structure = get_structure_by_id(struct_id)
        if structure:
            related_details.append({
                "id": structure["id"],
                "name": structure["name"],
                "category": structure["category"],
                "type": structure["type"],
                "location": structure["location"],
                "region": structure.get("region")
            })
    return related_details

REGIONS = [
    {"id": "head", "label": "Head", "primary": "skull"},
    {"id": "neck", "label": "Neck", "primary": "trachea"},
    {"id": "chest", "label": "Chest", "primary": "heart"},
    {"id": "abdomen", "label": "Abdomen", "primary": "liver"},
    {"id": "pelvis", "label": "Pelvis", "primary": None},
    {"id": "shoulder", "label": "Shoulder", "primary": None},
    {"id": "upper_arm", "label": "Upper Arm", "primary": None},
    {"id": "forearm", "label": "Forearm", "primary": None},
    {"id": "hand", "label": "Hand", "primary": None},
    {"id": "thigh", "label": "Thigh", "primary": "femur"},
    {"id": "knee", "label": "Knee", "primary": "patella"},
    {"id": "leg", "label": "Leg", "primary": "tibia"},
    {"id": "foot", "label": "Foot", "primary": None},
    {"id": "back", "label": "Back", "primary": "spinal_cord"},
]

def get_region(region_id: str):
    """Returns a region definition by ID."""
    for region in REGIONS:
        if region["id"] == region_id:
            return region
    return None

def get_structures_for_region(region_id: str):
    """Returns all structures that belong to a given body region."""
    matches = []
    for system in ANATOMY_DATA.get("systems", []):
        for structure in system.get("structures", []):
            if structure.get("region") == region_id:
                matches.append(structure)
    return matches

def get_layers():
    """Returns distinct anatomical layers present in the dataset for layer toggling."""
    layers = []
    seen = set()
    for system in ANATOMY_DATA.get("systems", []):
        layer = system["id"]
        if layer not in seen:
            seen.add(layer)
            layers.append({"id": layer, "name": system["name"]})
    return layers
