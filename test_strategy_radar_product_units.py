import unittest
from application.strategy_radar.product_units import FieldMapping, _format, format_ost_value, product_catalog


def mapping(**changes):
    value={'product':'CASH_SHARE','field':'entry','broker_field_label':'Limit price',
           'input_unit':'ZAR','output_unit':'ZAR_CENTS','decimal_places':0,
           'evidence_ref':'local-reviewed/field-evidence','observed_at':'2026-11-06T10:00:00+02:00','verified':True}
    value.update(changes)
    return FieldMapping(**value)


class ProductUnitTests(unittest.TestCase):
    def test_every_product_defaults_to_unavailable_and_metadata_distinct(self):
        catalog=product_catalog()
        self.assertEqual(set(catalog),{'CASH_SHARE','CFD','ETF','SSF','OPTION','FOREX'})
        for product in catalog:
            self.assertEqual(format_ost_value(product,'entry','123.45','ZAR')['state'],'UNAVAILABLE')
            self.assertEqual(catalog[product]['ost_mapping_state'],'UNVERIFIED')
        self.assertIn('expiry',catalog['SSF']['required_terms'])
        self.assertIsNone(catalog['ETF']['calculator'])

    def test_cents_conversion_and_no_silent_rounding(self):
        m=mapping(); reg={(m.product,m.field):m}
        result=_format('CASH_SHARE','entry','123.45','ZAR',reg)
        self.assertEqual(result['copy_value'],'12345')
        self.assertEqual(result['broker_field_label'],'Limit price')
        self.assertEqual(_format('CASH_SHARE','entry','123.456','ZAR',reg)['reason'],'VALUE_EXCEEDS_VERIFIED_PRECISION')
        self.assertEqual(_format('CASH_SHARE','stop_trigger','123.45','ZAR',reg)['reason'],'OST_FIELD_UNIT_UNVERIFIED')
        self.assertEqual(_format('CASH_SHARE','entry','123.45','ZAR_CENTS',reg)['reason'],'INPUT_UNIT_MISMATCH')

    def test_quantity_and_field_specific_precision(self):
        q=mapping(product='CFD',field='quantity',input_unit='CONTRACTS',output_unit='CONTRACTS',broker_field_label='Contracts')
        reg={(q.product,q.field):q}
        self.assertEqual(_format('CFD','quantity','7','CONTRACTS',reg)['copy_value'],'7')
        self.assertEqual(_format('CFD','quantity','7.5','CONTRACTS',reg)['reason'],'INVALID_VALUE')
        self.assertEqual(_format('CFD','quantity','NaN','CONTRACTS',reg)['reason'],'INVALID_VALUE')

    def test_evidence_and_product_unit_guards(self):
        with self.assertRaises(ValueError): mapping(evidence_ref='')
        with self.assertRaises(ValueError): mapping(observed_at='2026-11-06')
        with self.assertRaises(ValueError): mapping(verified=False)
        with self.assertRaises(ValueError): mapping(field='quantity')
        with self.assertRaises(ValueError): mapping(output_unit='CONTRACTS')
        with self.assertRaises(ValueError): mapping(field='trailing_percent')

if __name__=='__main__': unittest.main()
