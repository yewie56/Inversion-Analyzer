# -*- coding: utf-8 -*-
from pathlib import Path
WF=Path(__file__).parent/'.github'/'workflows'/'inversion_collect.yml'
LOC=Path(__file__).parent/'locations.json'

def check(name,cond,detail=''):
    if not cond: raise AssertionError(f'FAIL | {name} | {detail}')
    print(f'PASS | {name}')

def main():
    text=WF.read_text(encoding='utf-8')
    check('globaler KIT-Schritt vorhanden','Global KIT reference archive' in text)
    check('globaler Schritt ruft kit-only genau einmal auf',text.count('python Inversion_Server.py --kit-only')==1,text.count('python Inversion_Server.py --kit-only'))
    check('scheduled mode unverändert','MANUAL SCHEDULED COLLECTION' in text and 'INVERSION_LOCATION="$LOC" python Inversion_Server.py --scheduled' in text)
    import json
    loc=json.loads(LOC.read_text(encoding='utf-8'))['locations']
    ref=lambda item: bool(item.get('kit_reference',item.get('country_code')=='DE'))
    check('Viernheim KIT-Referenz',ref(loc['Viernheim']) is True)
    check('Bremerhaven KIT-Referenz',ref(loc['Bremerhaven']) is True)
    check('Valencia ohne KIT-Referenz',ref(loc['Valencia']) is False)
    print('PASS | v0.15.22 workflow global KIT regression complete')
    return 0

if __name__=='__main__': raise SystemExit(main())
