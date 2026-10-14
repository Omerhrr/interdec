"""SQLAlchemy models — Interdec Platform (users, vendors, shippers, projects, shipments)."""
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, DateTime
from datetime import datetime
from .database import Base


def _id():
    import uuid
    return uuid.uuid4().hex[:12]


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    avatar = Column(String, default="")
    platform_role = Column(String, default="user")  # admin | user
    apps = Column(JSON, default=lambda: {})  # {facade:{access,role}, importflow:{access,role}, catalogues:{access}}
    active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)  # forced on demo/admin-set passwords
    notify_prefs = Column(JSON, nullable=True)  # email notification choices, see notify_mail.py
    created = Column(DateTime, default=datetime.utcnow)

    @property
    def platformRole(self):
        return self.platform_role

    @property
    def mustChangePassword(self):
        return bool(self.must_change_password)


class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")
    country = Column(String, default="")
    category = Column(String, default="")
    address = Column(String, default="")
    notes = Column(Text, default="")
    catalogs = Column(JSON, default=list)  # [{name,size,type,data(base64),uploaded}]
    created = Column(Integer, default=0)  # epoch ms (matching original)


class Shipper(Base):
    __tablename__ = "shippers"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")
    country = Column(String, default="")
    category = Column(String, default="")
    notes = Column(Text, default="")
    created = Column(Integer, default=0)


class ClearingAgent(Base):
    """Customs clearing agents (like shippers, but for the port side)."""
    __tablename__ = "clearing_agents"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")
    country = Column(String, default="")
    category = Column(String, default="")   # e.g. sea port, airport, land border
    notes = Column(Text, default="")
    created = Column(Integer, default=0)


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    client = Column(String, default="")
    description = Column(Text, default="")
    status = Column(String, default="Active")  # Active | Completed | On Hold
    created = Column(Integer, default=0)


class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(String, primary_key=True, index=True)
    ref = Column(String, nullable=False)
    company_id = Column(String, default="facade")  # facade | davinci | doortec
    project_id = Column(String, nullable=True)
    category = Column(String, default="")
    vendor_id = Column(String, nullable=True)
    shipper_id = Column(String, nullable=True)
    status = Column(String, default="order_placed")  # order_placed|under_production|in_transit|completed
    payment_terms = Column(String, nullable=True)  # Before Shipment | After Shipment
    eta = Column(String, default="")
    ship_method = Column(String, default="")
    description = Column(String, default="")
    production_days = Column(String, default="")
    value = Column(Float, default=0)
    currency = Column(String, default="USD")
    vendor_invoice = Column(JSON, nullable=True)  # {name,size,type,data,uploaded}
    packing_list = Column(JSON, nullable=True)
    shipper_invoice = Column(JSON, nullable=True)
    goods_confirmed = Column(Boolean, default=False)
    clearing_agent_id = Column(String, nullable=True)
    vendor_payments = Column(JSON, nullable=True)  # [{id, date, amount, kind, ref, note, by, ts}] in the shipment currency
    shipping_cost = Column(JSON, nullable=True)   # {currency, lines:[{id,label,amount}], invoiceRef, paid, paidOn, note}
    clearing_cost = Column(JSON, nullable=True)   # same + docs:[{name,size,type,data,uploaded}]
    eta_alerts = Column(JSON, nullable=True)  # ETA email reminder settings + what was sent (see eta_alerts.py)
    dates = Column(JSON, default=dict)  # {created,invoiceUploaded,packingReady,shipperSelected,shipped,shipperInvoiced,closed}
    created = Column(Integer, default=0)
    updated = Column(Integer, default=0)


class Quote(Base):
    __tablename__ = "quotes"
    id = Column(String, primary_key=True, index=True)
    number = Column(String, unique=True, index=True)  # IDF-YYYY-NNN, server-assigned
    project_id = Column(String, nullable=True)        # optional link to ImportFlow project
    project_name = Column(String, default="")         # snapshot at save time
    client_name = Column(String, default="")
    client_phone = Column(String, default="")
    client_email = Column(String, default="")
    sales_person = Column(String, default="")
    notes = Column(Text, default="")
    created = Column(Integer, default=0)
    updated = Column(Integer, default=0)


class QuoteRevision(Base):
    __tablename__ = "quote_revisions"
    id = Column(String, primary_key=True, index=True)
    quote_id = Column(String, index=True, nullable=False)
    rev = Column(Integer, default=0)                  # 0 = original, monotonic
    status = Column(String, default="draft")          # draft | sent | won | lost
    items = Column(JSON, default=list)                # pricing engine item dicts
    markup_pct = Column(Float, default=100)
    vat_pct = Column(Float, default=7.5)
    validity_days = Column(Integer, default=14)
    payment_terms = Column(Text, default="")
    note = Column(Text, default="")
    logistics_cost = Column(Float, default=0.0)       # transport & logistics add-on (migrated from legacy facade)
    logistics_location = Column(String, default="")
    status_note = Column(Text, default="")            # why it was won/lost (PO no., competitor, price...)
    currency = Column(String, default="NGN")          # every money figure on this revision is in this currency
    fx_rate = Column(Float, default=1.0)              # naira per 1 unit of `currency`, locked when priced
    cost = Column(Float, default=0)
    mk_amt = Column(Float, default=0)
    sub = Column(Float, default=0)
    vat_amt = Column(Float, default=0)
    total = Column(Float, default=0)                  # sub + vat + logistics_cost
    created = Column(Integer, default=0)
    updated = Column(Integer, default=0)


class FacadeSetting(Base):
    """Admin-editable pricing catalogue overrides (rates, glass, hardware, settings)."""
    __tablename__ = "facade_settings"
    key = Column(String, primary_key=True)            # rates | currencies | gc | acpPanels | hwItems | hwKits | sf | mosqRates | settings
    value = Column(JSON, default=dict)
    updated = Column(Integer, default=0)


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, default="")
    user_name = Column(String, default="")
    action = Column(String, default="")     # machine key, e.g. shipment.created
    detail = Column(String, default="")     # human readable line
    icon = Column(String, default="•")      # emoji shown in the feed
    ts = Column(Integer, default=0)         # epoch ms


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)    # recipient
    message = Column(String, default="")
    kind = Column(String, default="info")   # info | success | warning
    icon = Column(String, default="🔔")
    read = Column(Boolean, default=False)
    ts = Column(Integer, default=0)         # epoch ms


class EmailLog(Base):
    """Every outgoing email attempt: sent, failed or not configured."""
    __tablename__ = "email_log"
    id = Column(String, primary_key=True, index=True)
    to = Column(Text, default="")
    subject = Column(String, default="")
    kind = Column(String, default="")              # eta.before_3 | eta.on_day | eta.overdue | eta.changed | eta.test
    shipment_id = Column(String, nullable=True, index=True)
    status = Column(String, default="")            # sent | failed | not_configured
    error = Column(Text, default="")
    ts = Column(Integer, default=0)
