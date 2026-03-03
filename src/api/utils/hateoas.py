"""HATEOAS link builder for REST API responses."""


def build_links(
    resource_type: str, resource_id: int, base_url: str = "/api/v1"
) -> dict[str, str]:
    """Build HATEOAS links for a resource."""
    return {
        "self": f"{base_url}/{resource_type}/{resource_id}",
        "collection": f"{base_url}/{resource_type}",
    }
