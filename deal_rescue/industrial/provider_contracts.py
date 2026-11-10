"""Supplier and buyer-source plugin boundaries. No network, no supplier claims on credit."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Protocol,Sequence,Any

T,F,Z='T','F','Z'
@dataclass(frozen=True)
class Inquiry:
    spec_digest:str
    spec_revision:str
    process:str
    material:str
    quantity:int
    country_code:str
    required_by:str

class SupplierPlugin(Protocol):
    """Permissioned read-only access. Must not submit PO or upload CAD without explicit scope."""
    provider_id:str
    def discover(self,query:Inquiry)->Sequence[dict[str,Any]]:...
    def quote(self,query:Inquiry)->dict[str,Any]:...

class BuyerDemandPlugin(Protocol):
    """Permissioned, privacy-minimizing demand feed, never a buyer's signature."""
    source_id:str
    def opted_in_demands(self,spec_digest:str,spec_revision:str)->Sequence[dict[str,Any]]:...

MANDATORY_SUPPLIER_FIELDS=('provider_id','quote_id','spec_digest','spec_revision','process','material',
                           'quantity','moq_units','capacity_units','base_amount_cents','currency',
                           'valid_through','ship_country','delivery_by','source_url')

def preflight_quote(quote, inquiry: Inquiry, *, verifier=None):
    if not isinstance(quote,dict):return {'verdict':Z,'why':'NO_QUOTE'}
    missing=[k for k in MANDATORY_SUPPLIER_FIELDS if quote.get(k) in (None,'')]
    if missing:return {'verdict':Z,'why':'QUOTE_FIELDS_MISSING','fields':missing}
    for k,v in [('spec_digest',inquiry.spec_digest),('spec_revision',inquiry.spec_revision),
                ('process',inquiry.process),('material',inquiry.material),('ship_country',inquiry.country_code)]:
        if quote[k]!=v:return {'verdict':F,'why':'SCOPE_MISMATCH_'+k}
    n=inquiry.quantity
    if any(type(quote[k]) is not int or quote[k]<0 for k in ('quantity','moq_units','capacity_units','base_amount_cents')):
        return {'verdict':F,'why':'BAD_QUOTE_NUMERIC'}
    if quote['quantity']!=n or quote['moq_units']>n or quote['capacity_units']<n:
        return {'verdict':F,'why':'MOQ_OR_CAPACITY'}
    try:
        if date.fromisoformat(quote['valid_through'])<date.today():return {'verdict':F,'why':'EXPIRED_QUOTE'}
        if date.fromisoformat(quote['delivery_by'])>date.fromisoformat(inquiry.required_by):return {'verdict':F,'why':'LATE_DELIVERY'}
    except (ValueError,TypeError):return {'verdict':Z,'why':'DATE_UNUSABLE'}
    if quote['currency']!='USD':return {'verdict':Z,'why':'CURRENCY_CONVERSION_NOT_CONFIRMED'}
    if not quote.get('own_shipping_per_buyer_cents') or not quote.get('seller_identity_receipt'):
        return {'verdict':Z,'why':'DELIVERY_OR_SELLER_IDENTITY_UNKNOWN'}
    # Manufacturer's quote is untrusted even if it includes a self-asserted verified flag.
    if verifier is None:return {'verdict':Z,'why':'INDEPENDENT_QUOTE_VERIFIER_UNAVAILABLE'}
    verdict=verifier(quote,inquiry)
    return {'verdict':T if verdict is True else F if verdict is False else Z,
            'why':'EXTERNAL_VERIFIER_DECISION'}
