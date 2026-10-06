"""Seed data - exact demo dataset extracted from the original app."""
import time
import uuid
from .database import SessionLocal, engine, Base
from . import models, pricing
from .auth import hash_password

DAY = 86400000  # ms
NOW = int(time.time() * 1000)


def seed_quotes(db):
    """Demo quotations, totals computed by the ported engine (golden case included)."""
    if db.query(models.Quote).count() > 0:
        return
    now = int(time.time() * 1000)
    catalog = pricing.DEFAULT_CATALOG
    s = pricing.SETTINGS_DEF

    def mk(number, client, phone, sales, status, items, markup=100.0, vat=7.5, days_ago=6):
        totals = pricing.calc_totals(items, markup, vat)
        q = models.Quote(
            id=uuid.uuid4().hex[:12], number=number, project_id=None, project_name="",
            client_name=client, client_phone=phone, client_email="", sales_person=sales,
            notes="", created=now - days_ago * DAY, updated=now - (days_ago - 2) * DAY,
        )
        rev = models.QuoteRevision(
            id=uuid.uuid4().hex[:12], quote_id=q.id, rev=0, status=status,
            items=[{k: v for k, v in it.items() if k != "bom"} for it in totals["items"]],
            markup_pct=markup, vat_pct=vat, validity_days=int(s["validity"]),
            payment_terms=s["paymentTerms"], note="",
            cost=totals["cost"], mk_amt=totals["mkAmt"], sub=totals["sub"],
            vat_amt=totals["vat"], total=totals["total"],
            created=now - days_ago * DAY, updated=now - (days_ago - 2) * DAY,
        )
        db.add(q)
        db.add(rev)
        return q, totals

    # Golden reference: audited E2E case (EUROTEC Single Casement 1200x1500 x10,
    # Tempered 8mm Clear) -> cost N1,666,000 -> +100% -> +7.5% VAT -> N3,581,900
    q1_items = [{
        "id": "it1", "product": "et_window", "subTypeId": "etw_single",
        "width": 1200, "height": 1500, "qty": 10,
        "glassTypeId": "tempered", "glassThickness": "8mm", "glassColour": "clear",
        "hasMosq": False, "hasSubframe": False, "elements": [], "note": "",
    }]
    mk("IDF-2026-001", "Lekki Towers Ltd", "+234 802 000 0001", "Chidi Okafor", "draft", q1_items, days_ago=8)

    q2_items = [
        {
            "id": "it1", "product": "et_door", "subTypeId": "etd_single",
            "width": 1000, "height": 2100, "qty": 2,
            "glassTypeId": "laminated", "glassThickness": "12.76mm (6+6)", "glassColour": "grey",
            "hasMosq": False, "hasSubframe": True, "elements": [], "note": "Main entrance",
        },
        {
            "id": "it2", "product": "et_cw", "subTypeId": "etcw_g",
            "width": 3000, "height": 2400, "qty": 1,
            "glassTypeId": "dgu", "glassThickness": "6+12A+6",
            "glassDguOuter": "lowe", "glassDguInner": "clear",
            "hasMosq": False, "hasSubframe": True, "elements": [], "note": "Ground floor south elevation",
        },
    ]
    mk("IDF-2026-002", "Mentor House Fit-out", "+234 803 000 0002", "Amaka Nwosu", "sent", q2_items, days_ago=5)
    db.commit()
    print("\u2713 Seeded: 2 demo quotes (IDF-2026-001 draft golden case, IDF-2026-002 sent)")


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_quotes(db)
        if db.query(models.User).count() > 0:
            return  # already seeded

        # --- Users ---
        users = [
            models.User(
                id="u_admin", name="Joshua Nwaorgu", email="joshua.n@interdecng.com",
                password_hash=hash_password("123456"), avatar="JN",
                platform_role="admin",
                apps={
                    "facade": {"access": True, "role": "admin"},
                    "importflow": {"access": True, "role": "admin"},
                    "catalogues": {"access": True},
                    "quotes": {"access": True, "role": "admin"},
                },
                active=True,
            ),
            models.User(
                id="u_sales", name="Sales Staff", email="sales@interdecng.com",
                password_hash=hash_password("sales123"), avatar="SS",
                platform_role="user",
                apps={
                    "facade": {"access": True, "role": "sales"},
                    "importflow": {"access": True, "role": "user"},
                    "catalogues": {"access": True},
                    "quotes": {"access": True, "role": "sales"},
                },
                active=True,
            ),
            models.User(
                id="u_viewer", name="Reports Viewer", email="viewer@interdecng.com",
                password_hash=hash_password("viewer123"), avatar="RV",
                platform_role="user",
                apps={
                    "facade": {"access": False, "role": "sales"},
                    "importflow": {"access": True, "role": "viewer"},
                    "catalogues": {"access": True},
                    "quotes": {"access": False, "role": "sales"},
                },
                active=True,
            ),
        ]
        db.add_all(users)

        # --- Vendors (from original demo data) ---
        vendors = [
            models.Vendor(id="vn1", name="Shanghai Apex Electronics", contact="Wei Chen", email="wei@apexelec.cn", phone="+86 21 5888 7200", country="China", category="Electronics", address="88 Zhangjiang Rd, Pudong, Shanghai", notes="Primary PCB supplier. 15-day lead.", catalogs=[], created=NOW - 90 * DAY),
            models.Vendor(id="vn2", name="Müller Maschinenbau GmbH", contact="Klaus Müller", email="k.muller@mullermb.de", phone="+49 711 2345 678", country="Germany", category="Machinery", address="Industriestr. 42, Stuttgart", notes="CNC tools. Annual maintenance.", catalogs=[], created=NOW - 200 * DAY),
            models.Vendor(id="vn3", name="Rajesh Textiles Pvt", contact="Priya Sharma", email="priya@rajeshtex.in", phone="+91 22 4567 8901", country="India", category="Textiles", address="Plot 17, MIDC, Mumbai", notes="Organic cotton. MOQ 500m.", catalogs=[], created=NOW - 120 * DAY),
            models.Vendor(id="vn4", name="Pacific Raw Materials Co.", contact="Tomoko Hayashi", email="t.hayashi@pacificraw.jp", phone="+81 3 6789 0123", country="Japan", category="Raw Materials", address="2-1-1 Nihonbashi, Tokyo", notes="JIS certified steel & aluminum.", catalogs=[], created=NOW - 300 * DAY),
            models.Vendor(id="vn5", name="Frutas del Sol S.A.", contact="María López", email="maria@frutasdelsol.mx", phone="+52 33 1234 5678", country="Mexico", category="Food & Beverage", address="Av. Vallarta 3200, Guadalajara", notes="Dried fruits. FDA approved.", catalogs=[], created=NOW - 45 * DAY),
            models.Vendor(id="vn6", name="Vetro Italia Glass", contact="Marco Rossi", email="m.rossi@vetroitalia.it", phone="+39 02 7654 321", country="Italy", category="Glass & Glazing", address="Via Milano 88, Murano", notes="Premium glass panels, custom sizes.", catalogs=[], created=NOW - 60 * DAY),
            models.Vendor(id="vn7", name="HardwarePro International", contact="Tom Baker", email="tom@hardwarepro.co.uk", phone="+44 121 456 7890", country="United Kingdom", category="Hardware", address="45 Industrial Park, Birmingham", notes="Door hinges, handles, locking systems.", catalogs=[], created=NOW - 80 * DAY),
        ]
        db.add_all(vendors)

        # --- Shippers ---
        shippers = [
            models.Shipper(id="sh1", name="Global Freight Logistics", contact="Ahmed Hassan", email="ahmed@globalfreight.ae", phone="+971 4 567 8901", country="UAE", category="Ocean Freight", notes="Full container loads, customs clearance.", created=NOW - 180 * DAY),
            models.Shipper(id="sh2", name="Nordic Express Cargo", contact="Lars Andersen", email="lars@nordicexpress.dk", phone="+45 33 12 3456", country="Denmark", category="Air Freight", notes="Express air freight, 3-day delivery.", created=NOW - 90 * DAY),
            models.Shipper(id="sh3", name="Maersk Line Agency", contact="Jan de Vries", email="j.devries@maerskagency.nl", phone="+31 10 234 5678", country="Netherlands", category="Ocean Freight", notes="Major ocean carrier, global routes.", created=NOW - 365 * DAY),
            models.Shipper(id="sh4", name="Hellenic Transport Co.", contact="Nikos Papadopoulos", email="nikos@hellenictrans.gr", phone="+30 210 678 9012", country="Greece", category="Multimodal", notes="Mediterranean routes, sea+land combo.", created=NOW - 60 * DAY),
        ]
        db.add_all(shippers)

        # --- Projects ---
        projects = [
            models.Project(id="pj1", name="Azrieli Tower Renovation", client="Azrieli Group", description="Full facade renovation of Tower 1, including glass panels and aluminum frames.", status="Active", created=NOW - 120 * DAY),
            models.Project(id="pj2", name="Tel Aviv Marina Hotel", client="Isrotel", description="New build hotel: doors, facade elements, interior hardware.", status="Active", created=NOW - 90 * DAY),
            models.Project(id="pj3", name="Haifa Port Terminal", client="Israel Ports Authority", description="Commercial terminal building: curtain wall facade system.", status="Active", created=NOW - 60 * DAY),
            models.Project(id="pj4", name="Jerusalem Cultural Center", client="Municipality of Jerusalem", description="Cultural center: specialty doors and glass installations.", status="Active", created=NOW - 45 * DAY),
            models.Project(id="pj5", name="Be'er Sheva Tech Park", client="Gav-Yam", description="Office complex Phase 2: automated door systems.", status="Completed", created=NOW - 200 * DAY),
        ]
        db.add_all(projects)

        # --- Shipments (full lifecycle demo) ---
        def finv(name, size, days_ago, type_="application/pdf"):
            return {"name": name, "size": size, "type": type_, "data": "", "uploaded": NOW - days_ago * DAY}

        shipments = [
            models.Shipment(id="sp1", ref="IMP-2026-001", company_id="facade", project_id="pj1", category="Glass & Glazing", vendor_id="vn6", shipper_id="sh1", status="completed", payment_terms="After Shipment", eta="15/02/26", ship_method="FCL", description="Glass Panels, Azrieli Tower Batch 1", production_days="45 days", value=48500, currency="USD",
                            vendor_invoice=finv("INV-VETRO-0221.pdf", 156000, 60), packing_list=finv("PL-VETRO-Crate-A1.xlsx", 87000, 45, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), shipper_invoice=finv("INV-GFL-4401.pdf", 134000, 15), goods_confirmed=True,
                            dates={"created": NOW - 75 * DAY, "invoiceUploaded": NOW - 60 * DAY, "packingReady": NOW - 45 * DAY, "shipperSelected": NOW - 40 * DAY, "shipped": NOW - 30 * DAY, "shipperInvoiced": NOW - 15 * DAY, "closed": NOW - 10 * DAY}, created=NOW - 75 * DAY, updated=NOW - 10 * DAY),
            models.Shipment(id="sp2", ref="IMP-2026-002", company_id="doortec", project_id="pj2", category="Hardware", vendor_id="vn7", shipper_id="sh3", status="in_transit", payment_terms="Before Shipment", eta="20/04/26", ship_method="LCL", description="Door Hardware Sets, Marina Hotel", production_days="21 days", value=18200, currency="USD",
                            vendor_invoice=finv("INV-HWP-8834.pdf", 145000, 30), packing_list=finv("PL-HWP-Pallet-B2.xlsx", 71000, 20, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), shipper_invoice=None, goods_confirmed=False,
                            dates={"created": NOW - 40 * DAY, "invoiceUploaded": NOW - 30 * DAY, "packingReady": NOW - 20 * DAY, "shipperSelected": NOW - 15 * DAY, "shipped": NOW - 8 * DAY}, created=NOW - 40 * DAY, updated=NOW - 8 * DAY),
            models.Shipment(id="sp3", ref="IMP-2026-003", company_id="facade", project_id="pj3", category="Raw Materials", vendor_id="vn4", shipper_id=None, status="under_production", payment_terms=None, eta="", ship_method="", description="Aluminum Frames, Haifa Port Terminal", production_days="60 days", value=67000, currency="EUR",
                            vendor_invoice=finv("INV-PRC-1187.pdf", 478000, 25), packing_list=finv("PL-PRC-Container.pdf", 134000, 5), shipper_invoice=None, goods_confirmed=False,
                            dates={"created": NOW - 35 * DAY, "invoiceUploaded": NOW - 25 * DAY, "packingReady": NOW - 5 * DAY}, created=NOW - 35 * DAY, updated=NOW - 5 * DAY),
            models.Shipment(id="sp4", ref="IMP-2026-004", company_id="davinci", project_id=None, category="Electronics", vendor_id="vn1", shipper_id=None, status="under_production", payment_terms=None, eta="", ship_method="", description="Electronic Control Boards, General Stock", production_days="30 days", value=12400, currency="USD",
                            vendor_invoice=finv("INV-APEX-445.pdf", 119000, 10), packing_list=None, shipper_invoice=None, goods_confirmed=False,
                            dates={"created": NOW - 15 * DAY, "invoiceUploaded": NOW - 10 * DAY}, created=NOW - 15 * DAY, updated=NOW - 10 * DAY),
            models.Shipment(id="sp5", ref="IMP-2026-005", company_id="doortec", project_id="pj4", category="Machinery", vendor_id="vn2", shipper_id=None, status="order_placed", payment_terms=None, eta="", ship_method="", description="Automatic Door Mechanisms, Jerusalem CC", production_days="90 days", value=42000, currency="USD",
                            vendor_invoice=None, packing_list=None, shipper_invoice=None, goods_confirmed=False,
                            dates={"created": NOW - 3 * DAY}, created=NOW - 3 * DAY, updated=NOW - 3 * DAY),
            models.Shipment(id="sp6", ref="IMP-2026-006", company_id="facade", project_id="pj1", category="Glass & Glazing", vendor_id="vn6", shipper_id="sh2", status="in_transit", payment_terms="After Shipment", eta="28/03/26", ship_method="Air D2D", description="Glass Panels, Azrieli Tower Batch 2", production_days="45 days", value=52300, currency="USD",
                            vendor_invoice=finv("INV-VETRO-0298.pdf", 203000, 50), packing_list=finv("PL-VETRO-Crate-A2.xlsx", 64000, 35, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), shipper_invoice=finv("INV-NEC-7782.pdf", 98000, 3), goods_confirmed=False,
                            dates={"created": NOW - 65 * DAY, "invoiceUploaded": NOW - 50 * DAY, "packingReady": NOW - 35 * DAY, "shipperSelected": NOW - 30 * DAY, "shipped": NOW - 12 * DAY, "shipperInvoiced": NOW - 3 * DAY}, created=NOW - 65 * DAY, updated=NOW - 3 * DAY),
            models.Shipment(id="sp7", ref="IMP-2026-007", company_id="davinci", project_id="pj2", category="Textiles", vendor_id="vn3", shipper_id="sh4", status="completed", payment_terms="Before Shipment", eta="10/02/26", ship_method="LCL", description="Interior Fabric Panels, Marina Hotel", production_days="14 days", value=9800, currency="USD",
                            vendor_invoice=finv("INV-RT-9012.pdf", 112000, 55), packing_list=finv("PL-RT-Bales.xlsx", 58000, 42, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), shipper_invoice=finv("INV-HTC-331.pdf", 76000, 20), goods_confirmed=True,
                            dates={"created": NOW - 70 * DAY, "invoiceUploaded": NOW - 55 * DAY, "packingReady": NOW - 42 * DAY, "shipperSelected": NOW - 38 * DAY, "shipped": NOW - 28 * DAY, "shipperInvoiced": NOW - 20 * DAY, "closed": NOW - 16 * DAY}, created=NOW - 70 * DAY, updated=NOW - 16 * DAY),
        ]
        db.add_all(shipments)

        # Activity feed + notifications demo history
        acts = [
            ("u_admin", "Joshua Nwaorgu", "shipment.status", "IMP-2026-007: In Transit to Completed", "🔄", NOW - 16 * DAY),
            ("u_admin", "Joshua Nwaorgu", "shipment.upload", "IMP-2026-007: shipper invoice uploaded", "📄", NOW - 20 * DAY),
            ("u_sales", "Sales Staff", "shipment.upload", "IMP-2026-002: packing list uploaded", "📄", NOW - 25 * DAY),
            ("u_admin", "Joshua Nwaorgu", "vendor.created", "Created vendor HardwarePro International", "🏗", NOW - 80 * DAY),
            ("u_admin", "Joshua Nwaorgu", "project.created", "Created project Jerusalem Cultural Center", "📋", NOW - 45 * DAY),
            ("u_sales", "Sales Staff", "shipment.created", "Created shipment IMP-2026-006 (Glass Panels, Azrieli Tower Batch 2)", "📦", NOW - 65 * DAY),
        ]
        import uuid as _uuid
        for uid_, uname, act, det, ico, ts in acts:
            db.add(models.ActivityLog(id=_uuid.uuid4().hex[:12], user_id=uid_, user_name=uname,
                                      action=act, detail=det, icon=ico, ts=ts))
        for uid_ in ("u_admin", "u_sales", "u_viewer"):
            db.add(models.Notification(id=_uuid.uuid4().hex[:12], user_id=uid_,
                                       message="Welcome to the new Interdec Platform! Recent shipment and catalogue updates will appear here.",
                                       kind="info", icon="👋", ts=NOW - 2 * DAY, read=(uid_ == "u_viewer")))

        db.commit()
        print("✓ Seeded: 3 users, 7 vendors, 4 shippers, 5 projects, 7 shipments, activity + notifications")
    finally:
        db.close()
