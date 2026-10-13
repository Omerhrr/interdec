"""End-to-end API tests (FastAPI TestClient on a throwaway SQLite database).

Covers the audit fixes: app startup (vendors router), role enforcement,
shipment workflow rules, catalogue upload/download, quotes access, mosquito
net pricing, project relinking and safe file downloads.

Run:  cd backend && python -m pytest tests -v
"""
import base64

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402  (seeds the temp DB)

client = TestClient(app)


def _login(email, pwd):
    r = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    return _login("joshua.n@interdecng.com", "123456")


@pytest.fixture(scope="module")
def sales():
    return _login("sales@interdecng.com", "sales123")


@pytest.fixture(scope="module")
def viewer():
    return _login("viewer@interdecng.com", "viewer123")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_health_and_core_lists(admin):
    assert client.get("/api/health").json()["status"] == "ok"
    for path in ("/api/vendors", "/api/shippers", "/api/projects", "/api/shipments"):
        r = client.get(path, headers=admin)
        assert r.status_code == 200 and isinstance(r.json(), list) and r.json(), path


def test_unauthenticated_rejected():
    assert client.get("/api/vendors").status_code == 401
    assert client.get("/api/quotes").status_code == 401


def test_viewer_is_read_only(viewer):
    assert client.get("/api/shipments", headers=viewer).status_code == 200
    assert client.post("/api/projects", json={"name": "X"}, headers=viewer).status_code == 403
    assert client.delete("/api/shipments/sp1", headers=viewer).status_code == 403
    assert client.post("/api/vendors", json={"name": "X"}, headers=viewer).status_code == 403
    # viewer has neither quotes nor facade access
    assert client.get("/api/quotes", headers=viewer).status_code == 403
    # user list is admin-only
    assert client.get("/api/users", headers=viewer).status_code == 403


def test_vendor_crud_and_catalogue_roundtrip(sales):
    v = client.post("/api/vendors", json={"name": "  Test Glass Co  ", "category": "Glass & Glazing"}, headers=sales).json()
    assert v["name"] == "Test Glass Co" and v["catalogs"] == []
    pdf = b"%PDF-1.4 test"
    r = client.post(f"/api/vendors/{v['id']}/catalogs",
                    json=[{"name": "../evil\"name.pdf", "size": 1, "type": "application/pdf", "data": _b64(pdf)}],
                    headers=sales)
    assert r.status_code == 200, r.text
    cat = r.json()[0]
    assert "data" not in cat and cat["size"] == len(pdf) and "/" not in cat["name"] and '"' not in cat["name"]
    d = client.get(f"/api/vendors/{v['id']}/catalogs/0/download", headers=sales)
    assert d.status_code == 200 and d.content == pdf and d.headers["content-type"] == "application/pdf"
    assert client.delete(f"/api/vendors/{v['id']}/catalogs/0", headers=sales).json() == {"ok": True}
    assert client.get(f"/api/vendors/{v['id']}/catalogs", headers=sales).json() == []
    assert client.delete(f"/api/vendors/{v['id']}", headers=sales).status_code == 200


def test_vendor_in_use_cannot_be_deleted(admin):
    r = client.delete("/api/vendors/vn6", headers=admin)
    assert r.status_code == 400


def test_html_upload_is_never_served_inline(sales):
    v = client.post("/api/vendors", json={"name": "XSS Co"}, headers=sales).json()
    client.post(f"/api/vendors/{v['id']}/catalogs",
                json=[{"name": "x.html", "type": "text/html", "data": _b64(b"<script>alert(1)</script>")}],
                headers=sales)
    d = client.get(f"/api/vendors/{v['id']}/catalogs/0/download", headers=sales)
    assert d.headers["content-type"] == "application/octet-stream"
    assert d.headers["content-disposition"].startswith("attachment")


def test_invalid_base64_rejected(sales):
    v = client.post("/api/vendors", json={"name": "B64 Co"}, headers=sales).json()
    r = client.post(f"/api/vendors/{v['id']}/catalogs",
                    json=[{"name": "a.pdf", "type": "application/pdf", "data": "not base64!!"}], headers=sales)
    assert r.status_code == 400


def _file(name="doc.pdf"):
    return {"name": name, "size": 3, "type": "application/pdf", "data": _b64(b"abc")}


def test_shipment_workflow_is_enforced(sales):
    s = client.post("/api/shipments", json={
        "companyId": "facade", "category": "Hardware", "vendorId": "vn7", "description": "Workflow test",
    }, headers=sales).json()
    sid = s["id"]
    assert s["status"] == "order_placed" and s["ref"].startswith("IMP-")

    put = lambda body: client.put(f"/api/shipments/{sid}", json=body, headers=sales)  # noqa: E731
    assert put({"status": "in_transit"}).status_code == 400          # cannot skip production
    assert put({"packingList": _file()}).status_code == 400          # invoice first
    assert put({"vendorInvoice": _file()}).json()["status"] == "under_production"
    r = put({"shipperId": "sh1", "paymentTerms": "Before Shipment", "shipMethod": "FCL", "eta": "01/01/27"})
    assert r.json()["status"] == "under_production"                  # saving shipper no longer ships
    assert put({"status": "in_transit"}).status_code == 400          # needs packing list
    put({"packingList": _file()})
    assert put({"status": "in_transit"}).json()["status"] == "in_transit"
    assert put({"goodsConfirmed": True}).status_code == 400          # needs shipper invoice
    put({"shipperInvoice": _file()})
    done = put({"goodsConfirmed": True}).json()
    assert done["status"] == "completed" and done["goodsConfirmed"] and done["dates"].get("closed")
    assert put({"status": "order_placed"}).status_code == 400        # non-admin cannot reopen


def test_invalid_status_value_rejected(admin):
    assert client.put("/api/shipments/sp5", json={"status": "teleported"}, headers=admin).status_code == 422


def test_shipment_refs_unique_after_delete(sales):
    body = {"companyId": "doortec", "category": "Hardware", "vendorId": "vn7", "description": "Ref test"}
    a = client.post("/api/shipments", json=body, headers=sales).json()
    b = client.post("/api/shipments", json=body, headers=sales).json()
    client.delete(f"/api/shipments/{a['id']}", headers=sales)
    c = client.post("/api/shipments", json=body, headers=sales).json()
    refs = [s["ref"] for s in client.get("/api/shipments", headers=sales).json()]
    assert len(refs) == len(set(refs)) and c["ref"] != b["ref"]


def test_quotes_access_and_project_relink(sales):
    q = client.post("/api/quotes", json={"clientName": "Relink Ltd", "items": []}, headers=sales).json()
    r = client.put(f"/api/quotes/{q['id']}", json={"projectId": "pj2"}, headers=sales).json()
    assert r["projectId"] == "pj2" and r["projectName"] == "Tel Aviv Marina Hotel"
    assert client.put(f"/api/quotes/{q['id']}", json={"projectId": "nope"}, headers=sales).status_code == 400


def test_mosquito_net_rate_is_applied(admin):
    item = {"id": "m1", "product": "et_window", "subTypeId": "etw_s2", "width": 2000, "height": 1000, "qty": 1,
            "glassTypeId": "single", "glassThickness": "6mm", "glassColour": "clear", "hasMosq": True}
    assert client.post("/api/quotes/calculate", json={"items": [item]}, headers=admin).json()["items"][0]["bom"]["mosqCost"] == 0
    cat = client.get("/api/quotes/catalog", headers=admin).json()["values"]
    rates = dict(cat["mosqRates"], etw_s2=10000)
    assert client.put("/api/quotes/catalog/mosqRates", json={"value": rates}, headers=admin).status_code == 200
    bom = client.post("/api/quotes/calculate", json={"items": [item]}, headers=admin).json()["items"][0]["bom"]
    assert bom["mosqCost"] == 10000  # 2 m2 x 0.5 (sliding half-area) x 10,000


def test_saved_revision_keeps_its_priced_snapshot(admin):
    item = {"id": "g1", "product": "et_window", "subTypeId": "etw_single", "width": 1200, "height": 1500, "qty": 10,
            "glassTypeId": "tempered", "glassThickness": "8mm", "glassColour": "clear"}
    q = client.post("/api/quotes", json={"clientName": "Snapshot", "items": [item], "markupPct": 100, "vatPct": 7.5},
                    headers=admin).json()
    before = q["latest"]["items"][0]["bom"]["total"]
    cat = client.get("/api/quotes/catalog", headers=admin).json()["values"]
    r2 = dict(cat["rates"], fabRate=99999)
    client.put("/api/quotes/catalog/rates", json={"value": r2}, headers=admin)
    after = client.get(f"/api/quotes/{q['id']}", headers=admin).json()["latest"]["items"][0]["bom"]["total"]
    client.put("/api/quotes/catalog/rates", json={"value": cat["rates"]}, headers=admin)
    assert before == after == 1666000


def test_catalog_validation(admin):
    bad = {"defaultMarkup": 50, "minMarkup": 70, "vatRate": 7.5, "validity": 14}
    assert client.put("/api/quotes/catalog/settings", json={"value": bad}, headers=admin).status_code == 400
    assert client.put("/api/quotes/catalog/rates", json={"value": {"brandRates": {}}}, headers=admin).status_code == 400


def test_sent_revision_is_locked(admin):
    q = client.post("/api/quotes", json={"clientName": "Lock", "items": []}, headers=admin).json()
    rid = q["latest"]["id"]
    client.post(f"/api/quotes/{q['id']}/revisions/{rid}/status", json={"status": "sent"}, headers=admin)
    r = client.put(f"/api/quotes/{q['id']}/revisions/{rid}", json={"markupPct": 150}, headers=admin)
    assert r.status_code == 400
    assert client.post(f"/api/quotes/{q['id']}/revisions/{rid}/status", json={"status": "bogus"},
                       headers=admin).status_code == 422


def test_quote_export_filename_header(admin):
    q = client.get("/api/quotes", headers=admin).json()[0]
    r = client.get(f"/api/quotes/{q['id']}/export", headers=admin)
    assert r.status_code == 200 and "filename*=" in r.headers["content-disposition"]


def test_change_password_keeps_session_and_validates(sales):
    r = client.post("/api/auth/change-password", json={"currentPassword": "wrong", "newPassword": "abcdef"}, headers=sales)
    assert r.status_code == 401
    r = client.post("/api/auth/change-password", json={"currentPassword": "sales123", "newPassword": " pass word "},
                    headers=sales)
    assert r.status_code == 200
    _login("sales@interdecng.com", " pass word ")  # spaces are preserved, not stripped
    # demo passwords can't be set again
    r = client.post("/api/auth/change-password", json={"currentPassword": " pass word ", "newPassword": "sales123"},
                    headers=sales)
    assert r.status_code == 400
    me = client.get("/api/auth/me", headers=sales).json()
    assert me["mustChangePassword"] is False


def test_user_admin_rules(admin):
    r = client.post("/api/users", json={"name": "New Person", "email": "new@x.io", "password": "secret1",
                                        "apps": {"quotes": {"access": True, "role": "sales"}, "bogus": {"access": True}}},
                    headers=admin)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["apps"]["quotes"]["access"] is True and "bogus" not in u["apps"]
    assert client.post("/api/users", json={"name": "Bad", "email": "b@x.io", "password": "secret1",
                                           "apps": {"importflow": {"access": True, "role": "god"}}},
                       headers=admin).status_code == 400
    assert client.put("/api/users/u_admin", json={"platformRole": "user"}, headers=admin).status_code == 400
    assert client.delete(f"/api/users/{u['id']}", headers=admin).status_code == 200


def test_demo_password_forces_change():
    r = client.post("/api/auth/login", json={"email": "viewer@interdecng.com", "password": "viewer123"})
    assert r.json()["user"]["mustChangePassword"] is True


def test_admin_created_user_must_change_password(admin):
    u = client.post("/api/users", json={"name": "Temp", "email": "temp@x.io", "password": "temp123"}, headers=admin).json()
    assert u["mustChangePassword"] is True
    client.delete(f"/api/users/{u['id']}", headers=admin)


def test_composite_item_priced_with_elements(admin):
    base = {"id": "c1", "product": "et_window", "subTypeId": "etw_single", "width": 1000, "height": 1500, "qty": 2,
            "glassTypeId": "tempered", "glassThickness": "8mm", "glassColour": "clear", "hasSubframe": True}
    el = {"id": "e1", "product": "et_window", "subTypeId": "etw_fixed", "width": 600, "height": 1500,
          "glassTypeId": "tempered", "glassThickness": "8mm", "glassColour": "clear"}
    single = client.post("/api/quotes/calculate", json={"items": [base]}, headers=admin).json()["cost"]
    comp = client.post("/api/quotes/calculate", json={"items": [dict(base, elements=[el])]}, headers=admin).json()
    bom = comp["items"][0]["bom"]
    assert bom["isComposite"] and comp["cost"] > single
    # shared-edge sub-frame rule: 1.5 x (W + H) per frame x qty
    assert bom["sfPerimLm"] == round((1.5 * (1.0 + 1.5) + 1.5 * (0.6 + 1.5)) * 2, 3)


def test_client_export_hides_costs_and_internal_is_admin_only(admin, sales):
    from openpyxl import load_workbook
    import io
    q = client.get("/api/quotes", headers=admin).json()[0]
    wb = load_workbook(io.BytesIO(client.get(f"/api/quotes/{q['id']}/export", headers=sales).content))
    assert wb.sheetnames == ["Work Breakdown"]
    assert client.get(f"/api/quotes/{q['id']}/export?internal=true", headers=sales).status_code == 403
    wb2 = load_workbook(io.BytesIO(client.get(f"/api/quotes/{q['id']}/export?internal=true", headers=admin).content))
    assert "BOM Details" in wb2.sheetnames


def test_won_lost_needs_reason_and_records_it(admin):
    q = client.post("/api/quotes", json={"clientName": "Outcome Ltd", "items": []}, headers=admin).json()
    rid = q["latest"]["id"]
    url = f"/api/quotes/{q['id']}/revisions/{rid}/status"
    client.post(url, json={"status": "sent"}, headers=admin)
    assert client.post(url, json={"status": "won"}, headers=admin).status_code == 400
    r = client.post(url, json={"status": "won", "note": "PO-4471"}, headers=admin).json()
    assert r["status"] == "won" and r["statusNote"] == "PO-4471"
    # undo back to sent clears the note
    assert client.post(url, json={"status": "sent"}, headers=admin).json()["statusNote"] == ""


def test_fx_rates_shared_and_admin_only(admin, viewer):
    assert client.get("/api/settings/fx", headers=viewer).json()["rates"]["USD"] == 1
    assert client.put("/api/settings/fx", json={"rates": {"EUR": 1.1}}, headers=viewer).status_code == 403
    r = client.put("/api/settings/fx", json={"rates": {"EUR": 1.1, "USD": 5}}, headers=admin).json()
    assert r["rates"]["EUR"] == 1.1 and r["rates"]["USD"] == 1 and r["updatedBy"]
    assert client.put("/api/settings/fx", json={"rates": {"EUR": -1}}, headers=admin).status_code == 400


def test_activity_hides_sign_ins_by_default(admin):
    acts = client.get("/api/activity?limit=50", headers=admin).json()
    assert all(not a["action"].startswith("auth.") for a in acts)
    assert any(a["action"].startswith("auth.") for a in client.get("/api/activity?limit=50&include_auth=true", headers=admin).json())
