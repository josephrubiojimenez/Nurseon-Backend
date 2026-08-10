
# Backend/route/anatomy.py

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any

# Assuming anatomy_data.py is in the same directory or accessible via sys.path
# If anatomy_data is in Backend/data/, you might need:
# from ..data.anatomy_data import get_anatomy_data, get_system_by_id, get_structure_by_id, search_structures, get_related_structures
# For simplicity, let's assume it's directly importable or already structured.
# If not, we may need to adjust the import path.

# For now, let's assume we can import from data.anatomy_data
try:
    from data.anatomy_data import get_anatomy_data, get_system_by_id, get_structure_by_id, search_structures, get_related_structures, get_structures_for_region, get_region, get_layers
except ImportError:
    # Fallback or error handling if data module is not set up correctly
    # This mock data will be replaced once the actual data loading works
    print("Warning: Could not import anatomy_data. Using mock data.")
    def get_anatomy_data():
        return {
            "systems": [
                {"id": "mock_skeletal", "name": "Mock Skeletal System", "description": "Placeholder system."}
            ]
        }
    def get_system_by_id(system_id: str):
        if system_id == "mock_skeletal":
            return {"id": "mock_skeletal", "name": "Mock Skeletal System", "description": "Placeholder system."}
        return None
    def get_structure_by_id(structure_id: str):
        if structure_id == "mock_femur":
            return {
                "id": "mock_femur", "name": "Mock Femur", "category": "Mock Skeletal System", "type": "Long bone",
                "location": "Thigh", "function": "Supports weight.", "key_facts": ["Longest bone."],
                "anatomical_landmarks": [], "clinical_relevance": "Common fracture site.", "related_structures": []
            }
        return None
    def search_structures(query: str):
        return [{"id": "mock_femur", "name": "Mock Femur", "category": "Mock Skeletal System", "location": "Thigh"}]
    def get_related_structures(structure_ids: list[str]):
        return [{"id": "mock_femur", "name": "Mock Femur", "category": "Mock Skeletal System", "type": "Long bone", "location": "Thigh"}]


anatomy_router = APIRouter()

@anatomy_router.get("/systems")
async def get_all_systems():
    """Returns a list of all body systems."""
    data = get_anatomy_data()
    # Return only systems and their names/ids for navigation
    return [{"id": sys["id"], "name": sys["name"]} for sys in data.get("systems", [])]

@anatomy_router.get("/system/{system_id}")
async def get_system_details(system_id: str):
    """Returns details for a specific body system and its structures."""
    system = get_system_by_id(system_id)
    if not system:
        raise HTTPException(status_code=404, detail="Body system not found")
    
    # Return structures with simplified details for listing
    structures_list = []
    for struct in system.get("structures", []):
        structures_list.append({
            "id": struct["id"],
            "name": struct["name"],
            "category": struct["category"],
            "type": struct["type"],
            "location": struct["location"]
        })
    
    return {
        "id": system["id"],
        "name": system["name"],
        "description": system["description"],
        "structures": structures_list
    }

@anatomy_router.get("/structure/{structure_id}")
async def get_structure_details(structure_id: str):
    """Returns detailed information about a specific anatomical structure."""
    structure = get_structure_by_id(structure_id)
    if not structure:
        raise HTTPException(status_code=404, detail="Anatomical structure not found")
    
    # If related structures are present, fetch their brief details
    if structure.get("related_structures"):
        related_details = get_related_structures(structure["related_structures"])
        structure["related_structures_details"] = related_details
        
    return structure

@anatomy_router.get("/search")
async def search_anatomical_structures(query: str = Query(..., description="Search term for anatomical structures")):
    """Searches for anatomical structures by name."""
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    results = search_structures(query)
    if not results:
        return {"message": "No anatomical structures found matching your query."}
        
    return results

@anatomy_router.get("/structures")
async def get_all_structures():
    """Returns a lightweight list of every anatomical structure (for search + region mapping)."""
    data = get_anatomy_data()
    structures = []
    for system in data.get("systems", []):
        for struct in system.get("structures", []):
            structures.append({
                "id": struct["id"],
                "name": struct["name"],
                "category": struct["category"],
                "type": struct["type"],
                "location": struct["location"],
                "region": struct.get("region"),
            })
    return structures


@anatomy_router.get("/regions")
async def get_all_regions():
    """Returns a list of anatomical body regions with their primary structure."""
    return get_region_list()


@anatomy_router.get("/region/{region_id}")
async def get_region_details(region_id: str):
    """Returns a body region plus the structures located within it."""
    region = get_region(region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Body region not found")
    structural = []
    for system in get_anatomy_data().get("systems", []):
        for struct in system.get("structures", []):
            if struct.get("region") == region_id:
                structural.append({
                    "id": struct["id"],
                    "name": struct["name"],
                    "category": struct["category"],
                    "type": struct["type"],
                    "location": struct["location"],
                    "region": struct.get("region"),
                })
    return {"id": region["id"], "label": region["label"], "primary": region.get("primary"), "structures": structural}


@anatomy_router.get("/layers")
async def get_layers_endpoint():
    """Returns the distinct anatomical layers available for toggling."""
    return get_layers()


def get_region_list():
    from data.anatomy_data import REGIONS
    return [{"id": r["id"], "label": r["label"], "primary": r.get("primary")} for r in REGIONS]


# Endpoint to fetch details for multiple related structures by IDs
@anatomy_router.post("/structures/batch")
async def get_structures_batch(structure_ids: List[str]):
    """Fetches details for multiple anatomical structures by their IDs."""
    if not structure_ids:
        raise HTTPException(status_code=400, detail="Please provide a list of structure IDs.")
    return get_related_structures(structure_ids)
