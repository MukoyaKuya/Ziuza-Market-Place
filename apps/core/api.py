
from ninja import NinjaAPI, Schema

from apps.core.locations import get_counties, get_sub_counties, get_wards

api = NinjaAPI(
    title="Ziuza Marketplace API",
    version="1.0.0",
    description="High-performance API for Ziuza Artisan Marketplace powered by Django Ninja",
    docs_url="/docs",
)


class LocationOptionSchema(Schema):
    name: str
    code: str | None = None


class LocationResponseSchema(Schema):
    count: int
    items: list[str]


@api.get("/locations/counties", response=LocationResponseSchema, tags=["Locations"])
def list_counties(request):
    """Get list of all 47 Kenyan Counties."""
    counties = get_counties()
    return {"count": len(counties), "items": counties}


@api.get("/locations/sub-counties", response=LocationResponseSchema, tags=["Locations"])
def list_sub_counties(request, county: str):
    """Get list of sub-counties for a specific county."""
    sub_counties = get_sub_counties(county)
    return {"count": len(sub_counties), "items": sub_counties}


@api.get("/locations/wards", response=LocationResponseSchema, tags=["Locations"])
def list_wards(request, sub_county: str):
    """Get list of wards for a specific sub-county."""
    wards = get_wards(sub_county)
    return {"count": len(wards), "items": wards}
