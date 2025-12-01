# backend/immich.py
import httpx
import logging
from typing import List, Dict
from backend.database import get_all_settings

logger = logging.getLogger(__name__)

async def search_immich_photos(query: str) -> List[Dict[str, str]]:
    """
    Searches local Immich instance using its Smart Search (CLIP).
    Returns list of image URLs and thumbnails.
    """
    try:
        settings = await get_all_settings()
        base_url = settings.get("immich_url")
        api_key = settings.get("immich_api_key")
        
        if not base_url or not api_key or "YOUR_IMMICH" in api_key:
            return []

        # Remove trailing slash if present
        base_url = base_url.rstrip('/')
        
        async with httpx.AsyncClient() as client:
            headers = {"x-api-key": api_key, "Accept": "application/json"}
            
            # Use Immich Smart Search Endpoint
            resp = await client.get(
                f"{base_url}/api/search/smart",
                params={"query": query},
                headers=headers,
                timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            # Take top 5 results
            for item in data[:5]:
                asset_id = item.get("id")
                if asset_id:
                    # Construct URLs (assuming standard Immich paths)
                    # Thumbnail: /api/asset/thumbnail/{id}
                    # Full: /api/asset/file/{id}
                    results.append({
                        "id": asset_id,
                        "url": f"{base_url}/api/asset/file/{asset_id}",
                        "thumbnail": f"{base_url}/api/asset/thumbnail/{asset_id}",
                        "created_at": item.get("fileCreatedAt")
                    })
            
            return results

    except Exception as e:
        logger.error(f"Immich Search Failed: {e}")
        return []