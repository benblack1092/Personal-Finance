"""Unit tests for the parsing/import helpers."""
from app.importers.amazon_importer import parse_amazon
from app.importers.common import clean_merchant, parse_amount, parse_date
from app.importers.csv_importer import parse_csv, suggest_mapping
from app.importers.ofx_importer import parse_ofx
from app.schemas import ColumnMapping


def test_parse_amount_variants():
    assert parse_amount("$1,234.56") == 1234.56
    assert parse_amount("(12.00)") == -12.00
    assert parse_amount("-5") == -5.0
    assert parse_amount("5.00-") == -5.0
    assert parse_amount(42) == 42.0


def test_parse_date_formats():
    assert parse_date("01/15/2024").isoformat() == "2024-01-15"
    assert parse_date("2024-01-15").isoformat() == "2024-01-15"
    assert parse_date("15/01/2024", "%d/%m/%Y").isoformat() == "2024-01-15"


def test_clean_merchant_strips_noise():
    assert "Starbucks" in clean_merchant("POS PURCHASE STARBUCKS #1234 CA")
    assert clean_merchant("") == ""


def test_suggest_mapping_single_amount():
    m = suggest_mapping(["Date", "Description", "Amount"])
    assert m.date == "Date"
    assert m.description == "Description"
    assert m.amount == "Amount"


def test_suggest_mapping_debit_credit():
    m = suggest_mapping(["Post Date", "Payee", "Debit", "Credit"])
    assert m.debit == "Debit"
    assert m.credit == "Credit"
    assert m.amount is None


def test_parse_csv_single_amount():
    csv = b"Date,Description,Amount\n01/15/2024,STARBUCKS,-4.50\n01/16/2024,PAYCHECK,2000\n"
    mapping = ColumnMapping(date="Date", description="Description", amount="Amount")
    rows = parse_csv(csv, mapping, account_id=1)
    assert len(rows) == 2
    assert rows[0]["amount"] == -4.50
    assert rows[1]["amount"] == 2000.0
    # Every row gets a dedup id.
    assert rows[0]["external_id"] != rows[1]["external_id"]


def test_parse_csv_debit_credit_and_flip():
    csv = b"Date,Name,Debit,Credit\n01/15/2024,Rent,1500,\n01/20/2024,Refund,,50\n"
    mapping = ColumnMapping(date="Date", description="Name", debit="Debit", credit="Credit")
    rows = parse_csv(csv, mapping, account_id=1)
    assert rows[0]["amount"] == -1500.0  # debit -> negative
    assert rows[1]["amount"] == 50.0     # credit -> positive


def test_parse_csv_skips_invalid_rows():
    csv = b"Date,Description,Amount\n,,\nTotal,,999\n01/15/2024,Coffee,-3\n"
    mapping = ColumnMapping(date="Date", description="Description", amount="Amount")
    rows = parse_csv(csv, mapping, account_id=1)
    assert len(rows) == 1


def test_parse_amazon_new_format():
    csv = (
        b"Order Date,Order ID,Product Name,Total Owed,Quantity\n"
        b"2024-03-01,111-222,USB Cable,9.99,2\n"
        b"2024-03-02,111-333,Notebook,4.50,1\n"
    )
    rows = parse_amazon(csv, account_id=1)
    assert len(rows) == 2
    assert rows[0]["amount"] == -9.99
    assert rows[0]["merchant"] == "Amazon"
    assert "USB Cable" in rows[0]["description"]
    assert "(x2)" in rows[0]["description"]


def test_parse_amazon_legacy_format():
    csv = b"Order Date,Order ID,Title,Item Total\n03/01/2024,D01-1,Widget,$12.00\n"
    rows = parse_amazon(csv, account_id=1)
    assert rows[0]["amount"] == -12.00
    assert "Widget" in rows[0]["description"]


def test_parse_ofx():
    ofx = b"""OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20240115120000<TRNAMT>-4.50<FITID>ABC123<NAME>STARBUCKS</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20240116<TRNAMT>2000.00<FITID>DEF456<NAME>PAYROLL<MEMO>Direct Deposit</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    rows = parse_ofx(ofx, account_id=1)
    assert len(rows) == 2
    assert rows[0]["amount"] == -4.50
    assert rows[0]["external_id"] == "ABC123"
    assert rows[0]["txn_date"].isoformat() == "2024-01-15"
    assert rows[1]["amount"] == 2000.00
    assert "Direct Deposit" in rows[1]["description"]
