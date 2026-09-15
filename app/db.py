import sqlite3
import os
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "vendor_contract.db")

def get_client():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_client()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS contracts (
        id TEXT PRIMARY KEY,
        vendor_name TEXT,
        vendor_country TEXT,
        vendor_address TEXT,
        product_name TEXT,
        business_line TEXT,
        region TEXT,
        customer_scope TEXT,
        pricing_model TEXT,
        currency TEXT,
        revenue_definition TEXT,
        platform_share REAL,
        vendor_share REAL,
        settlement_cycle TEXT,
        refund_policy TEXT,
        tax_invoice_party TEXT,
        signer_name TEXT,
        signer_title TEXT,
        signer_email TEXT,
        signer_authorized INTEGER,
        status TEXT DEFAULT 'Draft',
        version INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS approvals (
        id TEXT PRIMARY KEY,
        contract_id TEXT,
        approver TEXT,
        version INTEGER,
        decision TEXT,
        comment TEXT,
        is_valid INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        contract_id TEXT,
        operator TEXT,
        action TEXT,
        version INTEGER,
        detail TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS signatures (
        id TEXT PRIMARY KEY,
        contract_id TEXT,
        signer_name TEXT,
        signer_email TEXT,
        cc TEXT,
        status TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        signed_at TIMESTAMP,
        archive_files TEXT
    );

    CREATE TABLE IF NOT EXISTS versions (
        id TEXT PRIMARY KEY,
        contract_id TEXT,
        version INTEGER,
        snapshot TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

init_db()