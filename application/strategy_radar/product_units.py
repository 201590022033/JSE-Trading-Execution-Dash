"""Product-specific metadata and evidence-gated OST manual-entry formatting.

This module does not access broker screens, place orders or accept a mapping
from an API request. Verified mappings are trusted, explicit server records;
none is pre-populated until the exact product and field have been inspected.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

PRODUCTS = {
    'CASH_SHARE': {'label':'Cash shares', 'quantity_unit':'shares', 'chart_price_unit':'ZAR',
                   'calculator':'CASH_SHARE_SCENARIO', 'required_terms':['account_brokerage','minimum_brokerage','actual_fee_schedule']},
    'CFD': {'label':'CFD', 'quantity_unit':'contracts', 'chart_price_unit':'ZAR',
            'calculator':'ONE_SHARE_PER_CONTRACT_CFD_SCENARIO',
            'required_terms':['contract_multiplier','margin','financing','brokerage','executable_spread']},
    'ETF': {'label':'ETF', 'quantity_unit':'units', 'chart_price_unit':'ZAR', 'calculator':None,
            'required_terms':['instrument_identity','product_fee_schedule','tax_treatment']},
    'SSF': {'label':'Single-stock future', 'quantity_unit':'contracts', 'chart_price_unit':None, 'calculator':None,
            'required_terms':['contract_size','price_unit','expiry','margin','fees','settlement']},
    'OPTION': {'label':'Option', 'quantity_unit':'contracts', 'chart_price_unit':None, 'calculator':None,
               'required_terms':['underlying','option_type','strike','expiry','multiplier','premium_unit','fees']},
    'FOREX': {'label':'Forex', 'quantity_unit':'lots_or_units', 'chart_price_unit':None, 'calculator':None,
              'required_terms':['currency_pair','contract_size','quote_unit','account_currency','conversion','spread','financing']},
}
FIELDS = ('entry','quantity','stop_trigger','stop_limit','target','trailing_distance','trailing_percent')
UNITS = {'ZAR','ZAR_CENTS','SHARES','CONTRACTS','UNITS','PERCENT','PRICE_POINTS'}


@dataclass(frozen=True)
class FieldMapping:
    product: str
    field: str
    broker_field_label: str
    input_unit: str
    output_unit: str
    decimal_places: int
    evidence_ref: str
    observed_at: str
    verified: bool

    def __post_init__(self):
        if self.product not in PRODUCTS or self.field not in FIELDS:
            raise ValueError('explicit supported product and field required')
        if not isinstance(self.broker_field_label,str) or not self.broker_field_label.strip():
            raise ValueError('exact observed field label required')
        if self.input_unit not in UNITS or self.output_unit not in UNITS:
            raise ValueError('known explicit field units required')
        if type(self.decimal_places) is not int or not 0<=self.decimal_places<=8:
            raise ValueError('explicit decimal precision required')
        if self.verified is not True:
            raise ValueError('mapping must be explicitly verified')
        if not isinstance(self.evidence_ref,str) or not self.evidence_ref.strip():
            raise ValueError('source evidence reference required')
        try:
            dt=datetime.fromisoformat(self.observed_at.replace('Z','+00:00'))
            if dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError('timezone required')
        except (ValueError, TypeError, AttributeError):
            raise ValueError('actual aware evidence timestamp required')
        # Conversion is only permitted where the actual field unit is verified.
        supported={(u,u) for u in UNITS}|{('ZAR','ZAR_CENTS'),('ZAR_CENTS','ZAR')}
        if (self.input_unit,self.output_unit) not in supported:
            raise ValueError('unsupported field unit conversion')
        expected={'quantity':{'SHARES','CONTRACTS','UNITS'},
                  'trailing_percent':{'PERCENT'},
                  'trailing_distance':{'ZAR','ZAR_CENTS','PRICE_POINTS'}}
        allowed=expected.get(self.field,{'ZAR','ZAR_CENTS','PRICE_POINTS'})
        if self.input_unit not in allowed or self.output_unit not in allowed:
            raise ValueError('units inappropriate to field')
        if self.field=='quantity' and (self.input_unit!=self.output_unit or self.decimal_places!=0):
            raise ValueError('quantity conversion and fractional quantities require separate evidence')


# This trusted registry may only be populated by reviewed field-specific
# broker evidence in code. Empty means unavailable, not zero or cents by guess.
VERIFIED_OST_MAPPINGS: Mapping[tuple[str,str], FieldMapping] = {}


def product_catalog():
    """Return standalone product metadata without claiming current entitlements."""
    return {key:{**value,'required_terms':list(value['required_terms']),
                 'ost_mapping_state':'UNVERIFIED' if not any(p==key for p,_ in VERIFIED_OST_MAPPINGS) else 'PARTIAL_VERIFIED'}
            for key,value in PRODUCTS.items()}


def _format(product, field, value, input_unit, mappings):
    if product not in PRODUCTS or field not in FIELDS:
        raise ValueError('unsupported product or field')
    mapping=mappings.get((product,field))
    if mapping is None:
        return {'state':'UNAVAILABLE','reason':'OST_FIELD_UNIT_UNVERIFIED','product':product,'field':field,
                'chart_value':None if value is None else str(value),'chart_unit':input_unit,'copy_value':None}
    if not isinstance(mapping,FieldMapping) or (mapping.product,mapping.field)!=(product,field):
        raise ValueError('invalid trusted mapping')
    if input_unit!=mapping.input_unit:
        return {'state':'UNAVAILABLE','reason':'INPUT_UNIT_MISMATCH','product':product,'field':field,
                'chart_value':None if value is None else str(value),'chart_unit':input_unit,'copy_value':None}
    try:
        if value is None or isinstance(value,bool): raise ValueError('missing value')
        decimal=Decimal(str(value))
        if not decimal.is_finite() or decimal<=0: raise ValueError('positive finite value required')
        if field=='quantity' and decimal!=decimal.to_integral_value(): raise ValueError('whole quantity required')
        if mapping.input_unit=='ZAR' and mapping.output_unit=='ZAR_CENTS': decimal*=100
        elif mapping.input_unit=='ZAR_CENTS' and mapping.output_unit=='ZAR': decimal/=100
        quantized=decimal.quantize(Decimal(1).scaleb(-mapping.decimal_places))
        if quantized!=decimal:
            return {'state':'UNAVAILABLE','reason':'VALUE_EXCEEDS_VERIFIED_PRECISION','product':product,'field':field,
                    'chart_value':str(value),'chart_unit':input_unit,'copy_value':None}
    except (ValueError, InvalidOperation, TypeError):
        return {'state':'UNAVAILABLE','reason':'INVALID_VALUE','product':product,'field':field,
                'chart_value':None if value is None else str(value),'chart_unit':input_unit,'copy_value':None}
    return {'state':'VERIFIED','product':product,'field':field,'chart_value':str(value),'chart_unit':input_unit,
            'broker_field_label':mapping.broker_field_label,'broker_unit':mapping.output_unit,
            'copy_value':format(quantized, f'.{mapping.decimal_places}f'),
            'evidence_ref':mapping.evidence_ref,'observed_at':mapping.observed_at,'live_execution':False}


def format_ost_value(product, field, value, input_unit):
    """Return copy text only for a field in the trusted verified registry."""
    return _format(product,field,value,input_unit,VERIFIED_OST_MAPPINGS)
