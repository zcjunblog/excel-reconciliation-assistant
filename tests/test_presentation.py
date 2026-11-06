from datetime import datetime
from decimal import Decimal
import json
import unittest
from comparison_helpers import cell
from presentation import compact, original_value, ExactNumber


class PresentationTests(unittest.TestCase):
    def test_json_never_presents_a_binary_float_as_exact_original_number(self):
        data=json.loads(compact({'raw':0.1,'exact':Decimal('0.10000000000000000001')}))
        self.assertEqual(data['raw'],{'type':'float','value':'0.1'})
        self.assertEqual(data['exact'],{'type':'decimal','value':'0.10000000000000000001'})

    def test_native_iso_and_numeric_date_display_source_lexeme(self):
        iso='2026-11-06T08:09:10.123456+08:00'
        self.assertEqual(original_value(cell(datetime(2026,11,6,8,9,10),kind='date',date_lexeme=iso)),iso)
        self.assertEqual(original_value(cell(datetime(1900,1,1),kind='date',lexeme='1.000000000001')),'Excel日期序号 1.000000000001')

    def test_excel_unsafe_precision_is_explicit_text(self):
        text='12345678901234567890.12345678901234567890'
        self.assertEqual(ExactNumber(text).excel(),(text,'@'))
        self.assertEqual(ExactNumber('0.01').excel(),(0.01,'0.00'))


if __name__=='__main__': unittest.main()
