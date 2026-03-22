"""Integration tests for the live Planet Mark and UVDB route contracts."""


class TestPlanetMarkApiContracts:
    async def test_planet_mark_dashboard_contract(self, client, auth_headers):
        response = await client.get("/api/v1/planet-mark/dashboard", headers=auth_headers)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        payload = response.json()
        if payload.get("error_class") == "SETUP_REQUIRED":
            assert payload["module"] == "planet-mark"
            return
        assert "current_year" in payload
        assert "historical_years" in payload

    async def test_planet_mark_years_contract(self, client, auth_headers):
        response = await client.get("/api/v1/planet-mark/years", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        if payload.get("error_class") == "SETUP_REQUIRED":
            assert payload["module"] == "planet-mark"
            return
        assert "years" in payload
        assert "total" in payload

    async def test_planet_mark_actions_and_scope3_contracts(self, client, auth_headers):
        actions_response = await client.get("/api/v1/planet-mark/years/1/actions", headers=auth_headers)
        assert actions_response.status_code == 200
        actions_payload = actions_response.json()
        if actions_payload.get("error_class") == "SETUP_REQUIRED":
            assert actions_payload["module"] == "planet-mark"
        else:
            assert "actions" in actions_payload

        scope3_response = await client.get("/api/v1/planet-mark/years/1/scope3", headers=auth_headers)
        assert scope3_response.status_code == 200
        scope3_payload = scope3_response.json()
        if scope3_payload.get("error_class") == "SETUP_REQUIRED":
            assert scope3_payload["module"] == "planet-mark"
        else:
            assert "categories" in scope3_payload


class TestUvdbApiContracts:
    async def test_uvdb_dashboard_contract(self, client, auth_headers):
        response = await client.get("/api/v1/uvdb/dashboard", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert "summary" in payload
        assert "protocol" in payload

    async def test_uvdb_sections_contract(self, client, auth_headers):
        response = await client.get("/api/v1/uvdb/sections", headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert "sections" in payload
        assert "total_sections" in payload

    async def test_uvdb_audits_and_iso_mapping_contracts(self, client, auth_headers):
        audits_response = await client.get("/api/v1/uvdb/audits?skip=0&limit=5", headers=auth_headers)
        assert audits_response.status_code == 200
        audits_payload = audits_response.json()
        if audits_payload.get("error_class") == "SETUP_REQUIRED":
            assert audits_payload["module"] == "uvdb"
        else:
            assert "audits" in audits_payload

        mapping_response = await client.get("/api/v1/uvdb/iso-mapping", headers=auth_headers)
        assert mapping_response.status_code == 200
        assert "mappings" in mapping_response.json()
