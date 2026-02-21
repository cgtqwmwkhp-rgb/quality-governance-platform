"""HATEOAS link generation utilities."""

from pydantic import BaseModel


class Link(BaseModel):
    href: str
    method: str = "GET"


class ResourceLinks(BaseModel):
    self_link: Link

    class Config:
        populate_by_name = True


def build_resource_links(request_url: str, resource_type: str, resource_id: int | str) -> dict:
    """Build HATEOAS links for a resource."""
    base = f"/api/v1/{resource_type}"
    return {
        "self": {"href": f"{base}/{resource_id}", "method": "GET"},
        "update": {"href": f"{base}/{resource_id}", "method": "PATCH"},
        "delete": {"href": f"{base}/{resource_id}", "method": "DELETE"},
        "collection": {"href": base, "method": "GET"},
    }


def build_collection_links(
    resource_type: str,
    page: int,
    per_page: int,
    total_pages: int,
) -> dict:
    """Build HATEOAS links for a paginated collection."""
    base = f"/api/v1/{resource_type}"
    links = {
        "self": {"href": f"{base}?page={page}&per_page={per_page}", "method": "GET"},
    }
    if page > 1:
        links["prev"] = {"href": f"{base}?page={page - 1}&per_page={per_page}", "method": "GET"}
    if page < total_pages:
        links["next"] = {"href": f"{base}?page={page + 1}&per_page={per_page}", "method": "GET"}
    links["first"] = {"href": f"{base}?page=1&per_page={per_page}", "method": "GET"}
    links["last"] = {"href": f"{base}?page={total_pages}&per_page={per_page}", "method": "GET"}
    return links
