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
        # 200 (data or setup_required) or 404 if year 1 not seeded in this environment
        assert actions_response.status_code in (200, 404)
        if actions_response.status_code == 200:
            actions_payload = actions_response.json()
            if actions_payload.get("error_class") == "SETUP_REQUIRED":
                assert actions_payload["module"] == "planet-mark"
            else:
                assert "actions" in actions_payload

        scope3_response = await client.get("/api/v1/planet-mark/years/1/scope3", headers=auth_headers)
        # 200 (data or setup_required) or 404 if year 1 not seeded in this environment
        assert scope3_response.status_code in (200, 404)
        if scope3_response.status_code == 200:
            scope3_payload = scope3_response.json()
            if scope3_payload.get("error_class") == "SETUP_REQUIRED":
                assert scope3_payload["module"] == "planet-mark"
            else:
                assert "categories" in scope3_payload

    async def test_planet_mark_export_contract(self, client, auth_headers):
        json_response = await client.get(
            "/api/v1/planet-mark/years/1/export?format=json",
            headers=auth_headers,
        )
        assert json_response.status_code in (200, 404)
        if json_response.status_code == 200:
            assert json_response.headers["content-type"].startswith("application/json")
            assert "attachment" in json_response.headers.get("content-disposition", "")
            payload = json_response.json()
            assert payload.get("export_kind") == "json_pack"
            assert "reporting_year" in payload

        xlsx_response = await client.get(
            "/api/v1/planet-mark/years/1/export?format=xlsx",
            headers=auth_headers,
        )
        assert xlsx_response.status_code in (200, 404)
        if xlsx_response.status_code == 200:
            content_type = xlsx_response.headers["content-type"]
            assert "spreadsheetml" in content_type or "octet-stream" in content_type
            assert len(xlsx_response.content) > 100


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
        assert payload["total_sections"] == 15
        assert payload["content_coverage"]["status"] == "partial"
        assert payload["content_coverage"]["loaded_sections"] == ["1", "2", "12", "13", "14", "15"]

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
