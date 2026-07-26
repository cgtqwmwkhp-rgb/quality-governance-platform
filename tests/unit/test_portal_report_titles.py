from src.api.routes.employee_portal import format_portal_report_title, humanize_customer_code


def test_humanize_customer_code_px299():
    assert humanize_customer_code("plantexpand_ltd") == "Plantexpand Ltd"
    assert humanize_customer_code("ukpn") == "UK Power Networks"


def test_format_portal_report_title_px318():
    assert format_portal_report_title("Near Miss - plantexpand_ltd") == "Near Miss - Plantexpand Ltd"
    assert format_portal_report_title("Hydraulic hose burst, Bay 3") == "Hydraulic hose burst, Bay 3"
